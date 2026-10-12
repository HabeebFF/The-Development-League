"""Protection Points API: the public table and team breakdowns; staff manage everything."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.league.models import MatchDay, Team
from common.permissions import IsStaff, PublicRead

from . import rules
from .models import Adjustment, Period, Task, TaskResult


def _team(t: Team) -> dict:
    return {
        "id": t.pk,
        "name": t.name,
        "tag": t.tag,
        "slug": t.slug,
        "logo": t.logo.url if t.logo else None,
        "primary_color": t.primary_color,
    }


def _period(p: Period) -> dict:
    return {"id": p.pk, "name": p.name, "starts_on": p.starts_on, "ends_on": p.ends_on}


def _is_staff(request) -> bool:
    u = request.user
    return bool(u and u.is_authenticated and u.is_league_staff)


def _task(t: Task) -> dict:
    return {
        "id": t.pk,
        "date": t.date,
        "title": t.title,
        "rule": t.rule,
        "params": t.params,
        "pp_done": t.pp_done,
        "pp_not_done": t.pp_not_done,
        "is_published": t.is_published,
    }


def _result(r: TaskResult) -> dict:
    return {
        "id": r.pk,
        "team": _team(r.team),
        "done": r.final,
        "auto_done": r.done,
        "override": r.override,
        "note": r.note,
        "count": r.count,
        "detail": r.detail,
        "evidence": r.evidence,
        "matches": len(r.matches),
        "pp": r.pp,
    }


def _pick_period(request) -> Period | None:
    pid = request.query_params.get("period", "").strip()
    if pid:
        if not pid.isdigit():
            raise ValidationError({"period": "Must be a number."})
        return get_object_or_404(Period, pk=pid)
    return rules.current_period(timezone.localdate())


def _latest_tasks(period: Period, staff: bool) -> list[Task]:
    """The newest day's tasks: today's, or the last day that had any."""
    qs = period.tasks.all() if staff else period.tasks.filter(is_published=True)
    today = timezone.localdate()
    day = qs.filter(date__gte=today).order_by("date").values_list("date", flat=True).first()
    day = day or qs.order_by("-date").values_list("date", flat=True).first()
    return list(qs.filter(date=day)) if day else []


class TableView(APIView):
    """``GET /pp``: the PP table of a period (``?period=``; default the current one)."""

    permission_classes = [PublicRead]

    def get(self, request):
        staff = _is_staff(request)
        period = _pick_period(request)
        periods = [_period(p) for p in Period.objects.all()]
        if period is None:
            return Response(
                {"period": None, "periods": periods, "rows": [], "tasks": [], "text": ""}
            )
        rows = rules.table(period, staff=staff)
        tasks = _latest_tasks(period, staff)
        return Response(
            {
                "period": _period(period),
                "periods": periods,
                "rows": [{**r, "team": _team(r["team"])} for r in rows],
                "tasks": [_task(t) for t in tasks],
                "text": rules.as_text(rows, tasks),
            }
        )


class TeamView(APIView):
    """``GET /pp/teams/<slug>``: how a team got its PP in a period, task by task."""

    permission_classes = [PublicRead]

    def get(self, request, slug: str):
        team = get_object_or_404(Team, slug=slug)
        period = _pick_period(request)
        if period is None:
            raise ValidationError({"period": "No PP period yet."})
        results = TaskResult.objects.filter(task__period=period, team=team).select_related(
            "task", "team"
        )
        if not _is_staff(request):
            results = results.filter(task__is_published=True)
        adjustments = period.adjustments.filter(team=team)
        lines = [
            {
                "kind": a.kind,
                "date": timezone.localtime(a.created_at).date(),
                "pp": a.pp,
                "reason": a.reason,
            }
            for a in adjustments
        ]
        tasks = [
            {**_task(r.task), "result": _result(r)}
            for r in results.order_by("-task__date", "task__order")
        ]
        total = sum(a.pp for a in adjustments) + sum(r.pp for r in results)
        return Response(
            {
                "team": _team(team),
                "period": _period(period),
                "pp": total,
                "adjustments": lines,
                "tasks": tasks,
            }
        )


# -- Staff ---------------------------------------------------------------------------------


class PeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Period
        fields = ["id", "name", "starts_on", "ends_on"]

    def validate(self, attrs):
        start = attrs.get("starts_on", getattr(self.instance, "starts_on", None))
        end = attrs.get("ends_on", getattr(self.instance, "ends_on", None))
        if start and end and end < start:
            raise ValidationError({"ends_on": "Ends before it starts."})
        return attrs


class PeriodAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaff]
    serializer_class = PeriodSerializer
    queryset = Period.objects.all()
    pagination_class = None

    @action(detail=True, methods=["post"])
    def starting(self, request, pk=None):
        """Starting PP from the pasted table ("1. BERSERK GEN — +4 PP" per line). Replaces the
        period's starting PP; ``?dry_run=1`` only shows what would be matched."""
        period = self.get_object()
        found, missing = rules.parse_table(str(request.data.get("text", "")))
        if not found and not missing:
            raise ValidationError({"text": "No lines like “1. TEAM NAME — +2 PP” found."})
        if not request.data.get("dry_run"):
            rules.set_starting(period, found, request.user)
        return Response(
            {
                "matched": [{"name": n, "team": _team(t), "pp": pp} for t, pp, n in found],
                "missing": missing,
                "saved": not request.data.get("dry_run"),
            }
        )


class TaskSerializer(serializers.ModelSerializer):
    match_days = serializers.PrimaryKeyRelatedField(
        many=True, queryset=MatchDay.objects.all(), required=False
    )
    period = serializers.PrimaryKeyRelatedField(queryset=Period.objects.all(), required=False)

    class Meta:
        model = Task
        fields = [
            "id", "period", "date", "match_days", "title", "rule", "params",
            "pp_done", "pp_not_done", "is_published", "order",
        ]  # fmt: skip

    def validate(self, attrs):
        day = attrs.get("date", getattr(self.instance, "date", None))
        if "period" not in attrs and not self.instance:
            period = Period.objects.filter(starts_on__lte=day, ends_on__gte=day).first()
            if not period:
                raise ValidationError(
                    {"period": "No PP period covers this date. Create one first."}
                )
            attrs["period"] = period
        rule = attrs.get("rule", getattr(self.instance, "rule", None))
        params = attrs.get("params", getattr(self.instance, "params", None)) or {}
        if not isinstance(params, dict):
            raise ValidationError({"params": "Must be an object."})
        need = {
            Task.Rule.ZONE_ALIVE: ["zone", "min_matches"],
            Task.Rule.DAY_POINTS: ["op", "value"],
            Task.Rule.DAY_KILLS: ["op", "value"],
            Task.Rule.PLACEMENT: ["top", "min_matches"],
        }.get(rule, [])
        missing = [k for k in need if k not in params]
        if missing:
            raise ValidationError({"params": f"Missing {', '.join(missing)}."})
        if "op" in need and params["op"] not in rules.OPS:
            raise ValidationError({"params": f"op must be one of {', '.join(rules.OPS)}."})
        for k in need:
            if k != "op" and (not isinstance(params[k], int) or params[k] < 0):
                raise ValidationError({"params": f"{k} must be a whole number."})
        return attrs


class TaskAdminViewSet(viewsets.ModelViewSet):
    """Tasks with every team's result (``?period=``, ``?date=``). Saving re-checks the task."""

    permission_classes = [IsStaff]
    serializer_class = TaskSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Task.objects.prefetch_related("match_days")
        params = self.request.query_params
        if params.get("period", "").isdigit():
            qs = qs.filter(period_id=params["period"])
        if params.get("date"):
            qs = qs.filter(date=params["date"])
        return qs

    def _out(self, task: Task) -> dict:
        results = task.results.select_related("team", "task")
        return {
            **self.get_serializer(task).data,
            "results": [
                _result(r) for r in sorted(results, key=lambda r: (-r.pp, r.team.name.casefold()))
            ],
        }

    def list(self, request, *args, **kwargs):
        return Response([self._out(t) for t in self.get_queryset()])

    def retrieve(self, request, *args, **kwargs):
        return Response(self._out(self.get_object()))

    def perform_create(self, serializer):
        rules.check_task(serializer.save())

    def perform_update(self, serializer):
        rules.check_task(serializer.save())

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        self.perform_create(s)
        return Response(self._out(s.instance), status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        s = self.get_serializer(
            self.get_object(), data=request.data, partial=kwargs.get("partial", False)
        )
        s.is_valid(raise_exception=True)
        self.perform_update(s)
        return Response(self._out(s.instance))

    @action(detail=True, methods=["post"])
    def recheck(self, request, pk=None):
        task = self.get_object()
        rules.check_task(task)
        return Response(self._out(task))

    @action(detail=False, methods=["post"])
    def copy(self, request):
        """Copy one day's tasks to another day (``from``, ``to`` dates)."""
        src, dst = request.data.get("from"), request.data.get("to")
        if not src or not dst:
            raise ValidationError({"to": "Give both dates."})
        made = []
        for t in Task.objects.filter(date=src):
            s = self.get_serializer(
                data={
                    "date": dst, "title": t.title, "rule": t.rule, "params": t.params,
                    "pp_done": t.pp_done, "pp_not_done": t.pp_not_done, "order": t.order,
                }
            )  # fmt: skip
            s.is_valid(raise_exception=True)
            task = s.save()
            rules.check_task(task)
            made.append(self._out(task))
        return Response(made, status=status.HTTP_201_CREATED)


class ResultAdminView(APIView):
    """Staff's done / not done for a team on a task (``override`` null goes back to the logs).

    ``POST /admin/pp/results`` with ``task``, ``team``, ``override`` and ``note``.
    """

    permission_classes = [IsStaff]

    def post(self, request):
        task = get_object_or_404(Task, pk=request.data.get("task"))
        team = get_object_or_404(Team, pk=request.data.get("team"))
        override = request.data.get("override")
        if override not in (True, False, None):
            raise ValidationError({"override": "true, false or null."})
        row, _ = TaskResult.objects.get_or_create(
            task=task, team=team, defaults={"detail": "Didn't play"}
        )
        row.override, row.note = override, str(request.data.get("note", ""))[:160]
        if override is None and not row.matches:
            row.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        row.pp = row.score()
        row.save()
        return Response(_result(row))


class AdjustmentSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source="team.name", read_only=True)

    class Meta:
        model = Adjustment
        fields = ["id", "period", "team", "team_name", "kind", "pp", "reason", "created_at"]
        read_only_fields = ["created_at"]


class AdjustmentAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaff]
    serializer_class = AdjustmentSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Adjustment.objects.select_related("team")
        period = self.request.query_params.get("period", "")
        return qs.filter(period_id=period) if period.isdigit() else qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
