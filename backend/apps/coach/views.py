from datetime import date

from django.conf import settings
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.league.models import Match, Team
from apps.maps.models import Map
from apps.results.models import MatchEvent
from common.permissions import HasFeature, IsStaff, IsTeamMemberOrStaff

from . import counter, writer
from .engine import load_games, team_profile
from .models import AiUsage, CoachReport, CounterPlan, KnowledgeEntry, WeaponName
from .reports import week_of, write_reports
from .rotate import map_advice
from .serializers import (
    CoachReportSerializer,
    CounterPlanSerializer,
    KnowledgeEntrySerializer,
    WeaponNameSerializer,
)


class KnowledgeEntryViewSet(viewsets.ModelViewSet):
    """The coach's knowledge base. Filter with ``?kind=``, ``?map=<slug>`` and ``?status=``.
    Changing an entry's status records who reviewed it."""

    permission_classes = [IsStaff]
    serializer_class = KnowledgeEntrySerializer
    pagination_class = None

    def get_queryset(self):
        qs = KnowledgeEntry.objects.select_related("map", "area", "updated_by", "reviewed_by")
        if wanted := self.request.query_params.get("status"):
            qs = qs.filter(status=wanted)
        if kind := self.request.query_params.get("kind"):
            qs = qs.filter(kind=kind)
        if map_slug := self.request.query_params.get("map"):
            qs = qs.filter(map__slug=map_slug)
        return qs

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_update(self, serializer):
        extra = {}
        new = serializer.validated_data.get("status")
        if new and new != serializer.instance.status:
            extra = {"reviewed_by": self.request.user, "reviewed_at": timezone.now()}
        serializer.save(updated_by=self.request.user, **extra)


class WeaponListView(APIView):
    """Every weapon number seen in kills or knocks, how often, and its name if staff gave one."""

    permission_classes = [IsStaff]

    def get(self, request):
        seen = (
            MatchEvent.objects.filter(weapon_id__isnull=False)
            .values("weapon_id")
            .annotate(
                kills=Count("id", filter=Q(kind=MatchEvent.Kind.KILL)),
                knocks=Count("id", filter=Q(kind=MatchEvent.Kind.KNOCK)),
            )
        )
        rows = {r["weapon_id"]: {**r, "name": "", "weapon_class": "", "note": ""} for r in seen}
        for w in WeaponName.objects.all():
            row = rows.setdefault(w.weapon_id, {"weapon_id": w.weapon_id, "kills": 0, "knocks": 0})
            row.update(WeaponNameSerializer(w).data)
        return Response(
            sorted(rows.values(), key=lambda r: (-(r["kills"] + r["knocks"]), r["weapon_id"]))
        )


class WeaponNameView(generics.GenericAPIView):
    """``PUT`` names a weapon number; ``DELETE`` forgets the name."""

    permission_classes = [IsStaff]
    serializer_class = WeaponNameSerializer

    def put(self, request, weapon_id: int):
        instance = WeaponName.objects.filter(weapon_id=weapon_id).first()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(weapon_id=weapon_id)
        return Response(
            serializer.data, status=status.HTTP_200_OK if instance else status.HTTP_201_CREATED
        )

    def delete(self, request, weapon_id: int):
        WeaponName.objects.filter(weapon_id=weapon_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TeamProfileView(APIView):
    """What the analysis engine found about a team: facts with the matches behind them.
    Staff only for now; teams get their own reports in a later step."""

    permission_classes = [IsStaff]

    def get(self, request, slug: str):
        team = get_object_or_404(Team, slug=slug)
        return Response({"team": team.name, **team_profile(team.pk)})


COACH = "assistant"  # the plan feature that turns the coach on for a team


class TeamReportsView(APIView):
    """A team's weekly reports, newest first. Only that team (and staff) can see them."""

    permission_classes = [HasFeature(COACH), IsTeamMemberOrStaff]

    def get_team(self) -> Team:
        return get_object_or_404(Team, slug=self.kwargs["slug"])

    def get(self, request, slug: str):
        reports = CoachReport.objects.filter(team=self.get_team()).select_related(
            "team", "edited_by"
        )
        if not request.user.is_league_staff:
            reports = reports.filter(is_published=True)
        return Response(CoachReportSerializer(reports, many=True).data)


class ReportView(generics.RetrieveUpdateAPIView):
    """One report. Staff can reword, drop or reorder its tasks, or hide it."""

    serializer_class = CoachReportSerializer
    queryset = CoachReport.objects.select_related("team", "edited_by")
    http_method_names = ["get", "patch"]
    permission_classes = [IsStaff]  # reading is wider: see get_permissions

    def get_permissions(self):
        if self.request.method == "GET":
            return [HasFeature(COACH)(), IsTeamMemberOrStaff()]
        return [IsStaff()]

    def get_team(self) -> Team:
        return self.get_object().team

    def get_object(self):
        report = super().get_object()
        user = self.request.user
        if not report.is_published and not user.is_league_staff:
            raise Http404
        return report

    def perform_update(self, serializer):
        serializer.save(edited_by=self.request.user)


class ReportListView(APIView):
    """Staff: every team's report for a week (``?week=YYYY-MM-DD``, default this week).
    ``POST`` writes them (reports staff have edited are kept)."""

    permission_classes = [IsStaff]

    def _week(self, request):
        raw = request.data.get("week") if request.method == "POST" else None
        raw = raw or request.query_params.get("week")
        try:
            day = date.fromisoformat(raw) if raw else timezone.localdate()
        except (TypeError, ValueError):
            day = timezone.localdate()
        return week_of(day)

    def get(self, request):
        week = self._week(request)
        reports = CoachReport.objects.filter(week_start=week).select_related("team", "edited_by")
        return Response(
            {"week_start": week, "reports": CoachReportSerializer(reports, many=True).data}
        )

    def post(self, request):
        week = self._week(request)
        written = write_reports(week)
        ai = CoachReport.objects.filter(week_start=week, writer__startswith="gemini:").count()
        return Response(
            {"week_start": week, "written": written, "ai_written": ai},
            status=status.HTTP_201_CREATED,
        )


class AiUsageView(APIView):
    """Staff: whether the AI writer is on, and what it has used today and this month."""

    permission_classes = [IsStaff]

    def get(self, request):
        today = AiUsage.objects.filter(created_at__date=timezone.localdate())
        recent = AiUsage.objects.all()[:20]
        return Response(
            {
                "on": settings.COACH_WRITER == "gemini" and bool(settings.GEMINI_API_KEY),
                "blocked": writer.unavailable(),
                "model": settings.GEMINI_MODEL,
                "today": today.count(),
                "daily_limit": settings.COACH_AI_DAILY_REQUESTS,
                "per_minute": settings.COACH_AI_PER_MINUTE,
                "month_cost_usd": float(writer.month_cost()),
                "monthly_cap_usd": settings.COACH_AI_MONTHLY_CAP_USD,
                "recent": [
                    {
                        "at": u.created_at,
                        "feature": u.feature,
                        "model": u.model,
                        "ok": u.ok,
                        "error": u.error,
                        "items": u.items,
                        "kept": u.kept,
                        "tokens": u.input_tokens + u.output_tokens,
                        "cost_usd": float(u.cost_usd),
                    }
                    for u in recent
                ],
            }
        )


def _played(team: Team) -> list[int]:
    return sorted(
        Match.objects.filter(status=Match.Status.PUBLISHED, team_results__team=team).values_list(
            "pk", flat=True
        )
    )


class CounterPlanView(APIView):
    """How a team can play against an opponent (``/coach/teams/<us>/counter/<them>``).
    Made on the first ask each week, and again when the opponent has played new matches."""

    permission_classes = [HasFeature(COACH), IsTeamMemberOrStaff]

    def get_team(self) -> Team:
        return get_object_or_404(Team, slug=self.kwargs["slug"])

    def get(self, request, slug: str, opponent: str):
        team = self.get_team()
        rival = get_object_or_404(Team, slug=opponent)
        if rival.pk == team.pk:
            return Response(
                {"detail": "Pick another team to plan against."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        week = week_of(timezone.localdate())
        theirs = _played(rival)
        plan = CounterPlan.objects.filter(team=team, opponent=rival, week_start=week).first()
        stale = plan is None or not plan.writer.startswith(counter.RULES)
        if stale or sorted(m["id"] for m in plan.matches) != theirs:
            games = load_games(sorted(set(theirs) | set(_played(team))))
            names = dict(Team.objects.values_list("pk", "name"))
            content = counter.build(games, team.pk, rival.pk, names)
            content["plays"], kept = writer.rewrite(
                "counter", content["plays"], content["facts"], team=team.name, opponent=rival.name
            )
            if kept:
                content["writer"] = f"{counter.RULES}+{writer.label()}"
            plan, _ = CounterPlan.objects.update_or_create(
                team=team, opponent=rival, week_start=week, defaults=content
            )
        return Response(CounterPlanSerializer(plan).data)


class RotationAdviceView(APIView):
    """When to rotate on a map, drop by drop (``/coach/maps/<slug>/rotate``)."""

    permission_classes = [HasFeature(COACH)]

    def get(self, request, slug: str):
        game_map = get_object_or_404(Map, slug=slug)
        return Response({"name": game_map.name, **map_advice(game_map.slug)})
