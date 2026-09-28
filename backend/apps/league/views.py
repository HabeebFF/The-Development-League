"""League API. Public reads (seasons, standings, fixtures, results, teams); staff manage."""

from django.db.models import F, Prefetch, ProtectedError, Q
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.results.models import StandingRow
from apps.results.standings import schedule_rebuild
from common.permissions import IsStaff, IsSuperAdmin

from .models import (
    Group,
    Match,
    MatchDay,
    Player,
    RosterEntry,
    ScoringRule,
    Season,
    Stage,
    Team,
    TeamAlias,
)
from .serializers import (
    GroupAdminSerializer,
    MatchAdminSerializer,
    MatchDayAdminSerializer,
    MatchDaySerializer,
    MatchDetailSerializer,
    MatchListSerializer,
    PlayerAdminSerializer,
    RosterEntrySerializer,
    ScoringRuleSerializer,
    SeasonAdminSerializer,
    SeasonDetailSerializer,
    SeasonListSerializer,
    StageAdminSerializer,
    StandingRowSerializer,
    TeamAdminSerializer,
    TeamAliasSerializer,
    TeamDetailSerializer,
    TeamPublicSerializer,
)


def _int_param(request, name: str) -> int | None:
    value = request.query_params.get(name, "").strip()
    if not value:
        return None
    if not value.isdigit():
        raise ValidationError({name: "Must be a number."})
    return int(value)


def _day_matches() -> Prefetch:
    return Prefetch(
        "matches",
        queryset=Match.objects.select_related("map").prefetch_related("team_results__team"),
    )


class PublicTeamViewSet(viewsets.ReadOnlyModelViewSet):
    """League teams, visible to everyone. ``?search=`` matches name or tag."""

    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        qs = Team.objects.filter(is_league_member=True)
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(tag__icontains=search))
        return qs

    def get_serializer_class(self):
        return TeamDetailSerializer if self.action == "retrieve" else TeamPublicSerializer


class TeamAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaff]
    serializer_class = TeamAdminSerializer
    lookup_field = "slug"

    def get_queryset(self):
        qs = Team.objects.prefetch_related("aliases")
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(tag__icontains=search)
                | Q(aliases__in_game_name__icontains=search)
            ).distinct()
        return qs


class TeamAliasViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaff]
    serializer_class = TeamAliasSerializer

    def get_queryset(self):
        qs = TeamAlias.objects.select_related("team", "season")
        team = self.request.query_params.get("team")
        return qs.filter(team__slug=team) if team else qs


class PlayerAdminViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Players are created from match results; staff can correct names and teams."""

    permission_classes = [IsStaff]
    serializer_class = PlayerAdminSerializer
    http_method_names = ["get", "patch"]

    def get_queryset(self):
        qs = Player.objects.select_related("current_team", "user")
        search = self.request.query_params.get("search", "").strip()
        if search.isdigit():
            qs = qs.filter(game_uid=int(search))
        elif search:
            qs = qs.filter(search_name__icontains=search.casefold())
        team = self.request.query_params.get("team")
        return qs.filter(current_team__slug=team) if team else qs


class RosterEntryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaff]
    serializer_class = RosterEntrySerializer

    def get_queryset(self):
        qs = RosterEntry.objects.select_related("player", "team", "season")
        params = self.request.query_params
        if params.get("team"):
            qs = qs.filter(team__slug=params["team"])
        if params.get("season"):
            qs = qs.filter(season__slug=params["season"])
        return qs


# -- public: seasons, standings, fixtures, match days, matches ---------------------------------


class SeasonViewSet(viewsets.ReadOnlyModelViewSet):
    """Seasons, newest first. ``/seasons/{slug}`` includes stages, groups and scoring."""

    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        qs = Season.objects.select_related("scoring_rule")
        if self.action != "list":
            qs = qs.prefetch_related("stages__groups__teams")
        return qs

    def get_serializer_class(self):
        return SeasonListSerializer if self.action == "list" else SeasonDetailSerializer

    @action(detail=True)
    def standings(self, request, slug=None):
        """One table: ``?match_day=`` beats ``?group=`` beats ``?stage=``; none = season."""
        season = self.get_object()
        match_day, group, stage = (
            _int_param(request, "match_day"),
            _int_param(request, "group"),
            _int_param(request, "stage"),
        )
        if match_day:
            get_object_or_404(MatchDay, pk=match_day, stage__season=season)
            scope = f"day:{match_day}"
        elif group:
            get_object_or_404(Group, pk=group, stage__season=season)
            scope = f"group:{group}"
        elif stage:
            get_object_or_404(Stage, pk=stage, season=season)
            scope = f"stage:{stage}"
        else:
            scope = "season"
        rows = StandingRow.objects.filter(season=season, scope=scope).select_related("team")
        updated = max((r.updated_at for r in rows), default=None)
        return Response(
            {
                "season": season.slug,
                "scope": scope,
                "tiebreakers": season.tiebreakers,
                "updated_at": updated,
                "rows": StandingRowSerializer(rows, many=True, context={"request": request}).data,
            }
        )

    @action(detail=True)
    def fixtures(self, request, slug=None):
        """Match days with their matches. ``?stage=``, ``?group=``, ``?upcoming=true``."""
        season = self.get_object()
        days = (
            MatchDay.objects.filter(stage__season=season)
            .select_related("stage", "group")
            .prefetch_related(_day_matches())
            .order_by("stage__order", "date", "number", "pk")
        )
        stage, group = _int_param(request, "stage"), _int_param(request, "group")
        if stage:
            days = days.filter(stage_id=stage)
        if group:
            days = days.filter(group_id=group)
        if request.query_params.get("upcoming") in ("1", "true"):
            days = days.filter(
                matches__status__in=[Match.Status.DRAFT, Match.Status.PROCESSING]
            ).distinct()
        page = self.paginate_queryset(days)
        data = MatchDaySerializer(page, many=True, context={"request": request}).data
        return self.get_paginated_response(data)


class MatchDayViewSet(viewsets.ReadOnlyModelViewSet):
    """Match days (``?season=slug``, ``?stage=id``); detail adds the day's standings."""

    permission_classes = [AllowAny]
    serializer_class = MatchDaySerializer

    def get_queryset(self):
        qs = (
            MatchDay.objects.select_related("stage__season", "group")
            .prefetch_related(_day_matches())
            .order_by("stage__season", "stage__order", "date", "number", "pk")
        )
        if self.request.query_params.get("season"):
            qs = qs.filter(stage__season__slug=self.request.query_params["season"])
        stage = _int_param(self.request, "stage")
        return qs.filter(stage_id=stage) if stage else qs

    def retrieve(self, request, *args, **kwargs):
        day = self.get_object()
        rows = StandingRow.objects.filter(scope=f"day:{day.pk}").select_related("team")
        data = self.get_serializer(day).data
        data["season"] = day.stage.season.slug
        data["standings"] = StandingRowSerializer(
            rows, many=True, context={"request": request}
        ).data
        return Response(data)


class MatchViewSet(viewsets.ReadOnlyModelViewSet):
    """Published matches. Filters: ``?season=slug&match_day=id&map=slug&team=slug``."""

    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = (
            Match.objects.filter(status=Match.Status.PUBLISHED)
            .select_related("map", "match_day__stage__season")
            .prefetch_related("team_results__team")
            .order_by(
                F("match_day__date").desc(nulls_last=True),
                "-match_day__number",
                "-number",
                "-pk",
            )
        )
        params = self.request.query_params
        if params.get("season"):
            qs = qs.filter(match_day__stage__season__slug=params["season"])
        match_day = _int_param(self.request, "match_day")
        if match_day:
            qs = qs.filter(match_day_id=match_day)
        if params.get("map"):
            qs = qs.filter(map__slug=params["map"])
        if params.get("team"):
            qs = qs.filter(team_results__team__slug=params["team"]).distinct()
        return qs

    def get_serializer_class(self):
        return MatchDetailSerializer if self.action == "retrieve" else MatchListSerializer


# -- staff: league structure -------------------------------------------------------------------


class RebuildStandingsMixin:
    """Rebuild the standings of every season an edit touches (before and after)."""

    def seasons_of(self, instance) -> set[int]:
        raise NotImplementedError

    def perform_create(self, serializer):
        serializer.save()
        schedule_rebuild(*self.seasons_of(serializer.instance))

    def perform_update(self, serializer):
        before = self.seasons_of(serializer.instance)
        serializer.save()
        schedule_rebuild(*before, *self.seasons_of(serializer.instance))

    def perform_destroy(self, instance):
        seasons = self.seasons_of(instance)
        try:
            instance.delete()
        except ProtectedError as exc:
            raise ValidationError(
                {"detail": "It still has matches. Move or delete those matches first."}
            ) from exc
        schedule_rebuild(*seasons)


class ScoringRuleViewSet(RebuildStandingsMixin, viewsets.ModelViewSet):
    permission_classes = [IsSuperAdmin]
    serializer_class = ScoringRuleSerializer
    queryset = ScoringRule.objects.order_by("name")

    def seasons_of(self, instance) -> set[int]:
        return set(instance.seasons.values_list("pk", flat=True)) if instance.pk else set()

    def perform_destroy(self, instance):
        if instance.seasons.exists():
            raise ValidationError({"detail": "A season uses this rule."})
        instance.delete()


class SeasonAdminViewSet(RebuildStandingsMixin, viewsets.ModelViewSet):
    permission_classes = [IsStaff]
    serializer_class = SeasonAdminSerializer
    lookup_field = "slug"
    queryset = Season.objects.select_related("scoring_rule")

    def seasons_of(self, instance) -> set[int]:
        return {instance.pk} if instance.pk else set()

    def perform_destroy(self, instance):
        if Match.objects.filter(match_day__stage__season=instance).exists():
            raise ValidationError({"detail": "This season has matches; it can't be deleted."})
        instance.delete()

    @action(detail=True, methods=["post"], url_path="rebuild-standings")
    def rebuild_standings(self, request, slug=None):
        season = self.get_object()
        schedule_rebuild(season.pk)
        return Response({"queued": True}, status=status.HTTP_202_ACCEPTED)


class StageAdminViewSet(RebuildStandingsMixin, viewsets.ModelViewSet):
    permission_classes = [IsStaff]
    serializer_class = StageAdminSerializer

    def get_queryset(self):
        qs = Stage.objects.select_related("season")
        season = self.request.query_params.get("season")
        return qs.filter(season__slug=season) if season else qs

    def seasons_of(self, instance) -> set[int]:
        return {instance.season_id}


class GroupAdminViewSet(RebuildStandingsMixin, viewsets.ModelViewSet):
    permission_classes = [IsStaff]
    serializer_class = GroupAdminSerializer

    def get_queryset(self):
        qs = Group.objects.select_related("stage").prefetch_related("teams")
        stage = _int_param(self.request, "stage")
        if stage:
            qs = qs.filter(stage_id=stage)
        season = self.request.query_params.get("season")
        return qs.filter(stage__season__slug=season) if season else qs

    def seasons_of(self, instance) -> set[int]:
        return {Stage.objects.values_list("season_id", flat=True).get(pk=instance.stage_id)}


class MatchDayAdminViewSet(RebuildStandingsMixin, viewsets.ModelViewSet):
    permission_classes = [IsStaff]
    serializer_class = MatchDayAdminSerializer

    def get_queryset(self):
        qs = MatchDay.objects.select_related("stage", "group")
        stage = _int_param(self.request, "stage")
        if stage:
            qs = qs.filter(stage_id=stage)
        season = self.request.query_params.get("season")
        return qs.filter(stage__season__slug=season) if season else qs

    def seasons_of(self, instance) -> set[int]:
        return {Stage.objects.values_list("season_id", flat=True).get(pk=instance.stage_id)}


class MatchAdminViewSet(RebuildStandingsMixin, viewsets.ModelViewSet):
    """Fixtures and match details. Results come from uploads; staff can hide a match
    from standings by setting it back to NEEDS_REVIEW."""

    permission_classes = [IsStaff]
    serializer_class = MatchAdminSerializer

    def get_queryset(self):
        qs = Match.objects.select_related("map", "match_day__stage__season").prefetch_related(
            "rotations"
        )
        params = self.request.query_params
        match_day = _int_param(self.request, "match_day")
        if match_day:
            qs = qs.filter(match_day_id=match_day)
        if params.get("season"):
            qs = qs.filter(match_day__stage__season__slug=params["season"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        return qs

    def seasons_of(self, instance) -> set[int]:
        return {
            MatchDay.objects.values_list("stage__season_id", flat=True).get(
                pk=instance.match_day_id
            )
        }
