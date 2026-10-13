"""League API. Public reads (seasons, standings, fixtures, results, teams); staff manage."""

from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, F, Prefetch, ProtectedError, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.results.models import StandingRow
from apps.results.standings import schedule_rebuild
from common.permissions import IsStaff, IsSuperAdmin, PublicRead

from .merge import MergeError, merge_teams
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
    """League teams, for everyone (see ``PUBLIC_SITE``). ``?search=`` matches name or tag."""

    permission_classes = [PublicRead]
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
        qs = Team.objects.prefetch_related("aliases").annotate(
            matches_played=Count("match_results", distinct=True)
        )
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(tag__icontains=search)
                | Q(aliases__in_game_name__icontains=search)
            ).distinct()
        return qs

    @action(detail=True, methods=["post"])
    def merge(self, request, slug=None):
        """Merge this team into ``{"into": slug}``: its results, names and people move over."""
        source = self.get_object()
        target = get_object_or_404(Team, slug=request.data.get("into") or "")
        try:
            result = merge_teams(source, target)
        except MergeError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(result)


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


# -- league data (public while PUBLIC_SITE is on): seasons, standings, fixtures, days, matches


class SeasonViewSet(viewsets.ReadOnlyModelViewSet):
    """Seasons, newest first. ``/seasons/{slug}`` includes stages, groups and scoring."""

    permission_classes = [PublicRead]
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

    permission_classes = [PublicRead]
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

    permission_classes = [PublicRead]

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


class AwardsView(APIView):
    """Top player, rusher, sniper and grenader of a week or month (``?period=week|month``,
    ``?date=`` any day in it; default: the period of the latest published match)."""

    permission_classes = [PublicRead]

    def get(self, request):
        from apps.results.awards import awards, latest_day

        kind = "month" if request.query_params.get("period") == "month" else "week"
        try:
            day = date.fromisoformat(request.query_params.get("date", ""))
        except ValueError:
            day = latest_day() or timezone.localdate()
        return Response(awards(kind, day))


class KillsView(APIView):
    """Kill list: every player's kills, knocks and headshot knocks, best first.

    ``?match=<id>`` one match, ``?session=<match day id>`` one session (``?session=latest``
    the newest), or ``?period=week|month&date=`` any day in it (default: the latest period).
    """

    permission_classes = [PublicRead]

    def get(self, request):
        from apps.results import killboard
        from apps.results.awards import latest_day

        params = request.query_params
        match = _int_param(request, "match")
        if match:
            return Response(
                killboard.for_match(
                    get_object_or_404(Match, pk=match, status=Match.Status.PUBLISHED)
                )
            )
        if "session" in params:
            day = None if params["session"] == "latest" else _int_param(request, "session")
            return Response(
                killboard.for_session(get_object_or_404(MatchDay, pk=day) if day else None)
            )
        kind = "month" if params.get("period") == "month" else "week"
        try:
            day = date.fromisoformat(params.get("date", ""))
        except ValueError:
            day = latest_day() or timezone.localdate()
        return Response(killboard.for_period(kind, day))


class RatingsView(APIView):
    """Player ratings out of 10 (see apps.results.ratings).

    ``?match=<id>`` one match, with how each rating was made; otherwise ``?date=`` one day's
    averages (default the latest day) and ``?session=<match day id>`` just that session (its
    day when no date is given).
    """

    permission_classes = [PublicRead]

    def get(self, request):
        from apps.results import ratings

        params = request.query_params
        match = _int_param(request, "match")
        if match:
            return Response(
                ratings.for_match(get_object_or_404(Match, pk=match, status=Match.Status.PUBLISHED))
            )
        session = _int_param(request, "session")
        try:
            day = date.fromisoformat(params.get("date", ""))
        except ValueError:
            day = None
        if session and day is None:
            day = ratings.day_of_session(get_object_or_404(MatchDay, pk=session))
        return Response(ratings.for_day(day, session))


class PlayerRatingsView(APIView):
    """One player's daily ratings and their averages over the last 7 and 30 days."""

    permission_classes = [PublicRead]

    def get(self, request, player_id: int):
        from apps.results import ratings

        return Response(ratings.for_player(get_object_or_404(Player, pk=player_id)))


class RatingAdminView(APIView):
    """Staff: the points behind player ratings (GET; PUT ``{"points": {...}}`` saves them and
    rates every match again; POST rates every match again without changing anything)."""

    permission_classes = [IsStaff]

    def get(self, request):
        from apps.results.ratings import DEFAULT_POINTS, LIMITS, points

        return Response({"points": points(), "defaults": DEFAULT_POINTS, "limits": LIMITS})

    def put(self, request):
        from apps.results.models import RatingPoints
        from apps.results.ratings import LIMITS, PLACEMENT_LIMITS, points
        from apps.results.tasks import refresh_ratings_task

        given = request.data.get("points")
        if not isinstance(given, dict):
            raise ValidationError({"points": "Send {name: number}."})
        clean = {}
        for key, value in given.items():
            if key == "placement":
                low, high = PLACEMENT_LIMITS
                if (
                    not isinstance(value, list)
                    or not 1 <= len(value) <= 30
                    or not all(
                        isinstance(v, int | float) and not isinstance(v, bool) and low <= v <= high
                        for v in value
                    )
                ):
                    raise ValidationError(
                        {"points": f"placement must be a list of numbers from {low} to {high}."}
                    )
                clean[key] = [float(v) for v in value]
                continue
            if key not in LIMITS:
                raise ValidationError({"points": f"Unknown setting {key}."})
            low, high = LIMITS[key]
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not (low <= value <= high)
            ):
                raise ValidationError({"points": f"{key} must be a number from {low} to {high}."})
            clean[key] = int(value) if key == "potd_min" else float(value)
        merged = {**points(), **clean}
        if merged["floor"] >= merged["ceiling"]:
            raise ValidationError({"points": "The floor must be below the ceiling."})
        saved = RatingPoints.objects.first() or RatingPoints()
        saved.points = {**(saved.points or {}), **clean}
        saved.save()
        transaction.on_commit(lambda: refresh_ratings_task.delay(None, True))
        return self.get(request)

    def post(self, request):
        from apps.results.tasks import refresh_ratings_task

        refresh_ratings_task.delay(None, True)
        return Response({"queued": True}, status=status.HTTP_202_ACCEPTED)


# -- player cards (FUT style; see apps.results.cards) ----------------------------------------


def _media(f) -> str | None:
    return f.url if f else None


def _card(card, request) -> dict:
    """A card in its plain gold, silver or bronze. The special versions (Team of the Week and
    Month, Rising Star, Icon) only show on their own tabs, which set ``tier`` themselves."""
    from apps.results.cards import ROLE_LABELS, STATS, tier

    team, player = card.team, card.player
    return {
        "player_id": player.pk,
        "name": player.display_name,
        # The cut-out (background removed, framed head and shoulders) once it is made.
        "photo": _media(player.photo_cutout) or _media(player.photo),
        "cutout": bool(player.photo_cutout),
        "team": (
            {
                "id": team.pk,
                "name": team.name,
                "tag": team.tag,
                "slug": team.slug,
                "logo": _media(team.logo),
                "primary_color": team.primary_color,
            }
            if team
            else None
        ),
        "week": card.week,
        "role": card.role,
        "role_label": ROLE_LABELS.get(card.role, card.role),
        "role_suggested": card.role_suggested,
        "suggested_role": card.suggested_role,
        "overall": card.overall,
        "overall_change": card.overall_change,
        "tier": tier(card.overall),
        "totw": card.totw,
        "special": card.special,
        "rise": card.rise,
        "streak": card.streak,
        "stats": [{**s, "label": STATS.get(s["key"], s["key"])} for s in card.stats],
        "matches": card.matches,
        "week_matches": card.week_matches,
        "stale": card.stale,
    }


class CardsView(APIView):
    """Every player's card for a week (``?week=`` any day of it; default the latest week with
    cards), best first. ``?role=`` and ``?team=<slug>`` narrow it down."""

    permission_classes = [PublicRead]

    def get(self, request):
        from apps.results.cards import card_week
        from apps.results.models import PlayerCard

        weeks = list(
            PlayerCard.objects.filter(player__hide_card=False)
            .order_by("-week")
            .values_list("week", flat=True)
            .distinct()
        )
        try:
            week = card_week(date.fromisoformat(request.query_params.get("week", "")))
        except ValueError:
            week = weeks[0] if weeks else None
        qs = PlayerCard.objects.filter(week=week, player__hide_card=False).select_related(
            "player", "team"
        )
        role = request.query_params.get("role", "").upper()
        if role:
            qs = qs.filter(role=role)
        team = request.query_params.get("team", "").strip()
        if team:
            qs = qs.filter(team__slug=team)
        cards = sorted(qs, key=lambda c: (-c.overall, c.player.display_name.casefold()))
        older = [w for w in weeks if week and w < week]
        newer = [w for w in weeks if week and w > week]
        return Response(
            {
                "week": week,
                "end": week + timedelta(days=6) if week else None,
                "previous": older[0] if older else None,
                "next": newer[-1] if newer else None,
                "cards": [_card(c, request) for c in cards],
            }
        )


class CardSpecialsView(APIView):
    """A week's special cards (``?week=`` any day of it; default the newest week with cards):
    the Team of the Week, the Rising Stars and the Icons, plus every Icon run so far."""

    permission_classes = [PublicRead]

    def get(self, request):
        from apps.results.cards import (
            ICON,
            RISING_STAR,
            card_week,
            icon_hall,
            team_of_week,
            thresholds,
        )
        from apps.results.models import PlayerCard

        weeks = list(
            PlayerCard.objects.filter(player__hide_card=False)
            .order_by("-week")
            .values_list("week", flat=True)
            .distinct()
        )
        try:
            week = card_week(date.fromisoformat(request.query_params.get("week", "")))
        except ValueError:
            week = weeks[0] if weeks else None
        hall = [
            {
                "player_id": r["player"].pk,
                "name": r["player"].display_name,
                "photo": _media(r["player"].photo_cutout) or _media(r["player"].photo),
                "from": r["from"],
                "to": r["to"],
                "weeks": r["weeks"],
                "best": r["best"],
                "current": r["current"],
            }
            for r in icon_hall()
        ]
        if week is None:
            return Response(
                {"week": None, "end": None, "previous": None, "next": None, "newest": True,
                 "team_of_week": [], "rising": [], "icons": [], "hall": hall, "bars": thresholds()}
            )  # fmt: skip
        team = []
        for s in team_of_week(week):
            c = s.pop("card")
            team.append({**s, "card": {**_card(c, request), "tier": "totw"} if c else None})
        mine = PlayerCard.objects.filter(week=week, player__hide_card=False).select_related(
            "player", "team"
        )
        rising = sorted(mine.filter(special=RISING_STAR), key=lambda c: (-c.rise, -c.overall))
        icons = sorted(mine.filter(special=ICON), key=lambda c: (-c.streak, -c.overall))
        older = [w for w in weeks if w < week]
        newer = [w for w in weeks if w > week]
        return Response(
            {
                "week": week,
                "end": week + timedelta(days=6),
                "previous": older[0] if older else None,
                "next": newer[-1] if newer else None,
                # The newest cards start face down on the site.
                "newest": not newer,
                "team_of_week": team,
                "rising": [{**_card(c, request), "tier": "rising"} for c in rising],
                "icons": [{**_card(c, request), "tier": "icon"} for c in icons],
                "hall": hall,
                # What it takes: staff can change these.
                "bars": thresholds(),
            }
        )


class TeamOfMonthView(APIView):
    """Team of the Month: the month's top player, rusher, sniper and grenader on their latest
    card (``?month=`` any day of it; default the newest month with cards)."""

    permission_classes = [PublicRead]

    def get(self, request):
        from apps.results.awards import period_of
        from apps.results.cards import month_opens, months_with_cards, team_of_month

        months = months_with_cards()
        try:
            month = date.fromisoformat(request.query_params.get("month", "")).replace(day=1)
        except ValueError:
            month = months[0] if months else None
        if month is None:
            return Response({"month": None, "previous": None, "next": None, "slots": []})
        end = period_of("month", month)[1]
        opens = month_opens(end)
        # Until the month is over nobody sees who is in it, not even in the API: only the
        # slots, face down.
        locked = timezone.now() < opens
        slots = []
        for s in team_of_month(month):
            card = s.pop("card")
            if locked:
                slots.append({**s, "detail": "", "card": None})
                continue
            slots.append(
                {
                    **s,
                    "card": {**_card(card, request), "tier": "totm", "totm": s["award"]}
                    if card
                    else None,
                }
            )
        older = [m for m in months if m < month]
        newer = [m for m in months if m > month]
        return Response(
            {
                "month": month,
                "end": end,
                # Still being played: the cards stay locked until ``opens``.
                "finished": not locked,
                "locked": locked,
                "opens": opens,
                "newest": not newer,
                "previous": older[0] if older else None,
                "next": newer[-1] if newer else None,
                "slots": slots,
            }
        )


class PlayerCardView(APIView):
    """One player's latest card (or ``?week=``'s), and their overall week by week."""

    permission_classes = [PublicRead]

    def get(self, request, player_id: int):
        from apps.results.models import PlayerCard

        player = get_object_or_404(Player, pk=player_id, hide_card=False)
        cards = list(
            PlayerCard.objects.filter(player=player)
            .select_related("player", "team")
            .order_by("week")
        )
        if not cards:
            return Response({"detail": "This player has no card yet."}, status=404)
        pick = cards[-1]
        week = request.query_params.get("week")
        if week:
            pick = next((c for c in cards if str(c.week) == week), pick)
        return Response(
            {
                **_card(pick, request),
                "history": [{"week": c.week, "overall": c.overall, "role": c.role} for c in cards],
            }
        )


class CardAdminView(APIView):
    """Staff: card weights per role (GET, PUT ``{"weights": {role: {stat: n}}}``), the bars
    for Rising Stars and Icons (PUT ``{"specials": {rising_min, icon_min, icon_weeks}}``) and
    rebuilding a week's cards (POST ``{"week": "YYYY-MM-DD"}``, later weeks follow)."""

    permission_classes = [IsStaff]

    def get(self, request):
        from apps.results.cards import (
            DEFAULT_WEIGHTS,
            ROLE_LABELS,
            ROLE_STATS,
            STATS,
            thresholds,
            weights,
        )

        return Response(
            {
                "weights": weights(),
                "specials": thresholds(),
                "defaults": DEFAULT_WEIGHTS,
                "roles": [
                    {"key": r, "label": ROLE_LABELS[r], "stats": ROLE_STATS[r]} for r in ROLE_STATS
                ],
                "stats": STATS,
            }
        )

    def put(self, request):
        from apps.results.cards import ROLE_STATS
        from apps.results.models import CardWeights

        saved = CardWeights.objects.first() or CardWeights()
        if "specials" in request.data:
            self._specials(saved, request.data["specials"])
            if "weights" not in request.data:
                return self.get(request)
        given = request.data.get("weights")
        if not isinstance(given, dict):
            raise ValidationError({"weights": "Send {role: {stat: weight}}."})
        clean = {}
        for role, ws in given.items():
            if role not in ROLE_STATS or not isinstance(ws, dict):
                raise ValidationError({"weights": f"Unknown role {role}."})
            row = {}
            for key, value in ws.items():
                if key not in ROLE_STATS[role]:
                    raise ValidationError({"weights": f"{key} isn't on a {role.lower()} card."})
                try:
                    number = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValidationError({"weights": f"{key} must be a number."}) from exc
                if not 0 <= number <= 100:
                    raise ValidationError({"weights": f"{key} must be between 0 and 100."})
                row[key] = number
            if not any(row.values()):
                raise ValidationError({"weights": f"Give a {role.lower()} stat some weight."})
            clean[role] = row
        saved.weights = clean
        saved.save()
        return self.get(request)

    @staticmethod
    def _specials(saved, given) -> None:
        """New bars for Rising Stars and Icons, applied to every week's cards straight away."""
        from apps.results.cards import mark_specials
        from apps.results.models import PlayerCard

        limits = {"rising_min": (1, 59), "icon_min": (40, 99), "icon_weeks": (1, 52)}
        if not isinstance(given, dict) or not set(given) <= set(limits):
            raise ValidationError({"specials": "Send {rising_min, icon_min, icon_weeks}."})
        for key, value in given.items():
            low, high = limits[key]
            if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
                raise ValidationError(
                    {"specials": f"{key} must be a whole number from {low} to {high}."}
                )
            setattr(saved, key, value)
        saved.save()
        for week in PlayerCard.objects.order_by("week").values_list("week", flat=True).distinct():
            mark_specials(week)

    def post(self, request):
        from apps.results.tasks import rebuild_cards_task

        try:
            week = date.fromisoformat(str(request.data.get("week", "")))
        except ValueError as exc:
            raise ValidationError({"week": "Give a date: YYYY-MM-DD."}) from exc
        rebuild_cards_task.delay(week.isoformat())
        return Response({"queued": True, "week": week}, status=status.HTTP_202_ACCEPTED)
