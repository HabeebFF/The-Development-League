"""Tournament pages (public) and the staff tools: set up, invite, move days in, pay out."""

from __future__ import annotations

from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.league.models import MatchDay, Player, Team
from apps.results.models import PlayerMatchResult
from common.permissions import IsStaff, PublicRead

from . import services
from .models import PrizePayout, Tournament
from .services import TournamentError


def _team(t: Team | None) -> dict | None:
    if t is None:
        return None
    return {"id": t.pk, "name": t.name, "slug": t.slug, "tag": t.tag}


def _prizes(t: Tournament) -> list[dict]:
    """The prize table with the winners once the prizes are confirmed."""
    paid = {}
    if t.confirmed_at:
        for p in t.payouts.select_related("player", "team").order_by("pk"):
            paid.setdefault(p.prize_key, []).append(p)
    out = []
    for prize in t.prizes:
        places = services.places_of(prize["key"])
        winners = []
        keys = [f"place:{n}" for n in places] if places else [prize["key"]]
        for k in keys:
            shares = paid.get(k, [])
            if not shares:
                continue
            team = shares[0].team if places else None
            winners.append(
                {
                    "place": int(k.split(":")[1]) if places else None,
                    "team": _team(team),
                    "players": [s.player.display_name for s in shares],
                }
            )
        out.append(
            {
                **prize,
                "each": len(places) > 1,
                "cash_paid": prize["key"] in (t.cash_paid or []),
                "winners": winners,
            }
        )
    return out


def tournament_data(t: Tournament) -> dict:
    return {
        "id": t.pk,
        "name": t.name,
        "slug": t.slug,
        "season": t.season.slug,
        "stages": [{"id": s.pk, "name": s.name} for s in t.season.stages.order_by("order")],
        "starts_on": t.starts_on,
        "ends_on": t.ends_on,
        "format_note": t.format_note,
        "keyword": t.keyword,
        "status": services.status(t),
        "planned_matches": t.planned_matches,
        "matches": len(services.matches(t)),
        "teams": [_team(x) for x in t.teams.order_by("name")],
        "total_cash": services.total_cash(t.prizes),
        "total_dc": services.total_dc(t.prizes),
        "prizes": _prizes(t),
        "confirmed_at": t.confirmed_at,
    }


class TournamentListView(APIView):
    permission_classes = [PublicRead]

    def get(self, request):
        items = Tournament.objects.select_related("season").order_by("-starts_on", "-pk")
        return Response(
            [
                {
                    "name": t.name,
                    "slug": t.slug,
                    "starts_on": t.starts_on,
                    "ends_on": t.ends_on,
                    "status": services.status(t),
                    "keyword": t.keyword,
                    "stage": services.final_stage(t).pk,
                    "season": t.season.slug,
                }
                for t in items
            ]
        )


class TournamentView(APIView):
    permission_classes = [PublicRead]

    def get(self, request, slug):
        t = get_object_or_404(Tournament.objects.select_related("season"), slug=slug)
        return Response(tournament_data(t))


class TopPlayersView(APIView):
    """Most kills and best average rating over the tournament."""

    permission_classes = [PublicRead]

    def get(self, request, slug):
        from apps.results.ratings import board, points

        t = get_object_or_404(Tournament, slug=slug)
        played = services.matches(t)
        kills = list(
            PlayerMatchResult.objects.filter(match__in=played, player__isnull=False)
            .values("player", "player__display_name", "team__name")
            .annotate(k=Sum("kills"))
            .order_by("-k", "player__display_name")[:10]
        )
        rated = board(played, {**points(), "potd_min": 1}) if played else {"players": []}
        return Response(
            {
                "kills": [
                    {"player": r["player__display_name"], "team": r["team__name"], "kills": r["k"]}
                    for r in kills
                ],
                "ratings": [
                    {
                        "player": p["player"],
                        "team": p["team"]["name"] if p["team"] else None,
                        "rating": p["rating"],
                        "matches": p["matches"],
                    }
                    for p in rated["players"][:10]
                ],
            }
        )


# -- staff ---------------------------------------------------------------------------------------


class TournamentForm(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    starts_on = serializers.DateField(required=False, allow_null=True)
    ends_on = serializers.DateField(required=False, allow_null=True)
    keyword = serializers.CharField(max_length=40, required=False, allow_blank=True)
    format_note = serializers.CharField(max_length=300, required=False, allow_blank=True)
    planned_matches = serializers.IntegerField(min_value=1, max_value=200, required=False)
    prizes = serializers.JSONField(required=False)
    teams = serializers.ListField(child=serializers.IntegerField(), required=False)
    cash_paid = serializers.ListField(child=serializers.CharField(), required=False)


def _err(exc: TournamentError):
    raise ValidationError({"detail": str(exc)}) from exc


def _apply(t: Tournament, data: dict) -> Tournament:
    for f in ("name", "starts_on", "ends_on", "keyword", "format_note", "planned_matches"):
        if f in data:
            setattr(t, f, data[f])
    if "prizes" in data:
        if t.confirmed_at:
            raise ValidationError({"prizes": "The prizes were already paid."})
        try:
            t.prizes = services.clean_prizes(data["prizes"])
        except TournamentError as exc:
            _err(exc)
    if "cash_paid" in data:
        keys = {p["key"] for p in t.prizes}
        t.cash_paid = sorted(k for k in set(data["cash_paid"]) if k in keys)
    t.save()
    if "name" in data and t.season.name != t.name:
        t.season.name = t.name
        t.season.save(update_fields=["name", "updated_at"])
    if "teams" in data:
        if t.confirmed_at:
            raise ValidationError({"teams": "The prizes were already paid."})
        teams = list(Team.objects.filter(pk__in=data["teams"]))
        if len(teams) != len(set(data["teams"])):
            raise ValidationError({"teams": "Some of those teams don't exist."})
        t.teams.set(teams)
    return t


class StaffTournamentsView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        return Response([tournament_data(t) for t in Tournament.objects.select_related("season")])

    def post(self, request):
        form = TournamentForm(data=request.data)
        form.is_valid(raise_exception=True)
        data = dict(form.validated_data)
        try:
            t = services.create_tournament(
                data["name"],
                **{k: data[k] for k in ("starts_on", "ends_on", "keyword", "format_note",
                                        "planned_matches") if k in data},
            )  # fmt: skip
        except TournamentError as exc:
            _err(exc)
        _apply(t, {k: v for k, v in data.items() if k in ("prizes", "teams")})
        return Response(tournament_data(t), status=201)


class StaffTournamentView(APIView):
    permission_classes = [IsStaff]

    def get(self, request, slug):
        t = get_object_or_404(Tournament, slug=slug)
        days = (
            MatchDay.objects.filter(stage__season=t.season)
            .order_by("date", "number")
            .values("id", "title", "date", "number")
        )
        return Response({**tournament_data(t), "match_days": list(days)})

    def patch(self, request, slug):
        t = get_object_or_404(Tournament, slug=slug)
        form = TournamentForm(data=request.data, partial=True)
        form.is_valid(raise_exception=True)
        _apply(t, form.validated_data)
        return self.get(request, slug)


class InviteTopView(APIView):
    """Fill the teams with the top N of the league standings (default 12)."""

    permission_classes = [IsStaff]

    def post(self, request, slug):
        t = get_object_or_404(Tournament, slug=slug)
        n = request.data.get("n", 12)
        if not isinstance(n, int) or isinstance(n, bool) or not 2 <= n <= 64:
            raise ValidationError({"n": "Invite between 2 and 64 teams."})
        teams = services.top_teams(n)
        if not teams:
            raise ValidationError({"detail": "The league has no standings yet."})
        t.teams.set(teams)
        return Response(tournament_data(t))


class MoveDaysView(APIView):
    """Move match days from the league season into the tournament (and its table)."""

    permission_classes = [IsStaff]

    def get(self, request, slug):
        """League match days that could be moved: the newest first."""
        t = get_object_or_404(Tournament, slug=slug)
        league = services.scrim_season()
        days = (
            MatchDay.objects.filter(stage__season=league).order_by("-date", "-number")[:30]
            if league
            else []
        )
        word = (t.keyword or "").casefold()
        return Response(
            [
                {
                    "id": d.pk,
                    "title": str(d),
                    "date": d.date,
                    "suggested": bool(word) and word in (d.title or "").casefold(),
                }
                for d in days
            ]
        )

    def post(self, request, slug):
        t = get_object_or_404(Tournament, slug=slug)
        ids = request.data.get("match_days")
        if not isinstance(ids, list) or not ids or not all(isinstance(i, int) for i in ids):
            raise ValidationError({"match_days": "Pick the match days to move."})
        try:
            services.move_days(t, ids)
        except TournamentError as exc:
            _err(exc)
        return Response(tournament_data(t))


class PayoutView(APIView):
    """GET: who wins what (preview). POST: confirm and pay the DC, once."""

    permission_classes = [IsStaff]

    def get(self, request, slug):
        t = get_object_or_404(Tournament, slug=slug)
        if t.confirmed_at:
            rows = [
                {
                    "label": p.label,
                    "player": p.player.display_name,
                    "team": p.team.name if p.team else None,
                    "amount": p.amount,
                    "paid": p.paid_at is not None,
                }
                for p in t.payouts.select_related("player", "team")
            ]
            return Response({"confirmed": True, "confirmed_at": t.confirmed_at, "payouts": rows})
        return Response({"confirmed": False, **services.preview(t)})

    def post(self, request, slug):
        t = get_object_or_404(Tournament, slug=slug)
        igl = None
        if request.data.get("best_igl"):
            igl = get_object_or_404(Player, pk=request.data["best_igl"])
        try:
            result = services.confirm(t, request.user, best_igl=igl)
        except TournamentError as exc:
            _err(exc)
        return Response(result)


class HeldView(APIView):
    """Prizes waiting for a winner to make an account."""

    permission_classes = [IsStaff]

    def get(self, request, slug):
        t = get_object_or_404(Tournament, slug=slug)
        held = PrizePayout.objects.filter(tournament=t, paid_at__isnull=True)
        return Response(
            [
                {
                    "player": p.player.display_name,
                    "uid": p.player.game_uid,
                    "label": p.label,
                    "amount": p.amount,
                }
                for p in held.select_related("player")
            ]  # fmt: skip
        )
