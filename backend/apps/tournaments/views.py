"""Tournament pages (public) and the staff tools: set up, invite, move days in, pay out."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import NotAuthenticated, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.league.models import MatchDay, Player, Stage, Team
from apps.results.models import PlayerMatchResult
from common.permissions import IsStaff, PublicRead

from . import entries, services
from .models import Entry, PrizePayout, Tournament
from .services import TournamentError


def _team(t: Team | None) -> dict | None:
    if t is None:
        return None
    return {
        "id": t.pk,
        "name": t.name,
        "slug": t.slug,
        "tag": t.tag,
        "logo": t.logo.url if t.logo else None,
        "primary_color": t.primary_color,
    }


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
        "cancelled_at": t.cancelled_at,
        "registration": registration_data(t),
        "entries": entries_data(t),
    }


def registration_data(t: Tournament) -> dict:
    q = entries.qualifier_stage(t)
    return {
        "state": entries.reg_state(t),
        "opens_at": t.reg_opens_at,
        "closes_at": t.reg_closes_at,
        "fee": t.entry_fee,
        "places": t.places,
        "taken": entries.taken(t, q) if q else 0,
        "waitlist": Entry.objects.filter(
            tournament=t, stage=q, status=Entry.Status.WAITLIST
        ).count()
        if q
        else 0,
        "invite_count": t.invite_count,
        "qualify_count": t.qualify_count,
        "invited_at": t.invited_at,
        "advanced_at": t.advanced_at,
        "qualifier": {"id": q.pk, "name": q.name} if q else None,
        "final": {"id": services.final_stage(t).pk, "name": services.final_stage(t).name},
    }


def _entry(e: Entry, staff: bool = False) -> dict:
    row = {
        "id": e.pk,
        "team": _team(e.team),
        "stage": e.stage_id,
        "via": e.via,
        "status": e.status,
        "note": e.note,
    }
    if staff:
        row.update(
            {
                "fee_paid": e.fee_paid,
                "refunded": e.refunded,
                "paid_from": e.paid_from,
                "paid_by": e.paid_by.display_name if e.paid_by else None,
                "registered_by": e.registered_by.display_name if e.registered_by else None,
                "created_at": e.created_at,
            }
        )
    return row


def entries_data(t: Tournament, staff: bool = False) -> list[dict]:
    """Teams in (and waitlisted) per stage; staff also see who left and the fees."""
    rows = Entry.objects.filter(tournament=t).select_related("team", "paid_by", "registered_by")
    if not staff:
        rows = rows.filter(status__in=[Entry.Status.IN, Entry.Status.WAITLIST])
    rows = rows.order_by("stage__order", "status", "queued_at", "team__name")
    return [_entry(e, staff) for e in rows]


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
                    # Where new uploads go: the qualifier until its teams are sent through.
                    "stage": entries.current_stage(t).pk,
                    "stage_ids": list(t.season.stages.values_list("pk", flat=True)),
                    "season": t.season.slug,
                    "registration": entries.reg_state(t),
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
    reg_opens_at = serializers.DateTimeField(required=False, allow_null=True)
    reg_closes_at = serializers.DateTimeField(required=False, allow_null=True)
    entry_fee = serializers.IntegerField(min_value=0, max_value=100_000_000, required=False)
    places = serializers.IntegerField(min_value=2, max_value=200, required=False)
    invite_count = serializers.IntegerField(min_value=0, max_value=64, required=False)
    qualify_count = serializers.IntegerField(min_value=1, max_value=64, required=False)

    def validate(self, data):
        opens, closes = data.get("reg_opens_at"), data.get("reg_closes_at")
        if opens and closes and closes <= opens:
            raise serializers.ValidationError({"reg_closes_at": "Close after it opens."})
        return data


def _err(exc: TournamentError):
    raise ValidationError({"detail": str(exc)}) from exc


def _apply(t: Tournament, data: dict, actor=None) -> Tournament:
    for f in ("name", "starts_on", "ends_on", "keyword", "format_note", "planned_matches",
              "reg_opens_at", "reg_closes_at", "entry_fee", "places", "invite_count",
              "qualify_count"):  # fmt: skip
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
        try:
            entries.set_final_teams(t, data["teams"], actor)
        except TournamentError as exc:
            raise ValidationError({"teams": str(exc)}) from exc
    if "places" in data:
        with transaction.atomic():
            entries.fill(Tournament.objects.select_for_update().get(pk=t.pk))
            entries.sync_teams(t)
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
        _apply(t, {k: v for k, v in data.items() if k in ("prizes", "teams")}, request.user)
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
        return Response(
            {
                **tournament_data(t),
                "entries": entries_data(t, staff=True),
                "qualifier_table": entries.qualifier_top(t),
                "match_days": list(days),
            }
        )

    def patch(self, request, slug):
        t = get_object_or_404(Tournament, slug=slug)
        form = TournamentForm(data=request.data, partial=True)
        form.is_valid(raise_exception=True)
        _apply(t, form.validated_data, request.user)
        return self.get(request, slug)


class InviteTopView(APIView):
    """Invite the top N of the league standings into the final (default: the tournament's
    invite count with a qualifier, else 12), freezing the list."""

    permission_classes = [IsStaff]

    def post(self, request, slug):
        t = get_object_or_404(Tournament, slug=slug)
        n = request.data.get("n")
        if n is not None and (not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 64):
            raise ValidationError({"n": "Invite between 1 and 64 teams."})
        try:
            entries.invite_top(t, n, dc_wildcard=bool(request.data.get("dc_wildcard")))
        except TournamentError as exc:
            _err(exc)
        t.refresh_from_db()
        return Response(tournament_data(t))


class InviteNextView(APIView):
    """Invite the best team in the standings that isn't in yet (one declined)."""

    permission_classes = [IsStaff]

    def post(self, request, slug):
        t = get_object_or_404(Tournament, slug=slug)
        try:
            entries.invite_next(t)
        except TournamentError as exc:
            _err(exc)
        return Response(tournament_data(t))


class QualifierView(APIView):
    """Add a qualifier stage before the final, which turns registration on."""

    permission_classes = [IsStaff]

    def post(self, request, slug):
        t = get_object_or_404(Tournament, slug=slug)
        if t.confirmed_at or t.cancelled_at:
            raise ValidationError({"detail": "The tournament is over."})
        name = str(request.data.get("name") or "Qualifier").strip()[:80] or "Qualifier"
        entries.add_qualifier(t, name)
        return Response(tournament_data(t))


class StaffEntriesView(APIView):
    """POST {team, stage}: put a team in a stage for free."""

    permission_classes = [IsStaff]

    def post(self, request, slug):
        t = get_object_or_404(Tournament, slug=slug)
        team = get_object_or_404(Team, pk=request.data.get("team"))
        stage = get_object_or_404(Stage, pk=request.data.get("stage"))
        try:
            entries.staff_add(t, team, stage, request.user, str(request.data.get("note", "")))
        except TournamentError as exc:
            _err(exc)
        return Response(tournament_data(t))


class StaffRemoveEntryView(APIView):
    """POST {keep_fee}: take a team out, refunding its fee unless it's kept."""

    permission_classes = [IsStaff]

    def post(self, request, slug, pk):
        t = get_object_or_404(Tournament, slug=slug)
        entry = get_object_or_404(Entry, pk=pk, tournament=t)
        try:
            entries.staff_remove(
                t, entry, request.user, keep_fee=bool(request.data.get("keep_fee")),
                note=str(request.data.get("note", "")),
            )  # fmt: skip
        except TournamentError as exc:
            _err(exc)
        return Response(tournament_data(t))


class AdvanceView(APIView):
    """GET: the qualifier table and who goes through. POST {teams?}: send them to the final."""

    permission_classes = [IsStaff]

    def get(self, request, slug):
        t = get_object_or_404(Tournament, slug=slug)
        return Response({"qualify_count": t.qualify_count, "table": entries.qualifier_top(t)})

    def post(self, request, slug):
        t = get_object_or_404(Tournament, slug=slug)
        ids = request.data.get("teams")
        if ids is not None and (
            not isinstance(ids, list) or not all(isinstance(i, int) for i in ids)
        ):
            raise ValidationError({"teams": "Pick the teams."})
        try:
            entries.advance(t, request.user, ids)
        except TournamentError as exc:
            _err(exc)
        t.refresh_from_db()
        return Response(tournament_data(t))


class CancelView(APIView):
    permission_classes = [IsStaff]

    def post(self, request, slug):
        t = get_object_or_404(Tournament, slug=slug)
        try:
            back = entries.cancel(t, request.user)
        except TournamentError as exc:
            _err(exc)
        t.refresh_from_db()
        return Response({**tournament_data(t), "refunded": back})


# -- teams ---------------------------------------------------------------------------------------


def _my_team(request) -> Team | None:
    from apps.dc.perks import team_of

    slug = request.data.get("team") if request.method == "POST" else request.GET.get("team")
    if slug:
        return Team.objects.filter(slug=slug).first()
    return team_of(request.user) if request.user.is_authenticated else None


def my_entry_data(t: Tournament, request) -> dict:
    """The signed-in person's team in this tournament and what they can do."""
    from apps.dc.perks import pot_for
    from apps.predictions.services import wallet_for

    user, team = request.user, _my_team(request)
    out = {"registration": registration_data(t), "team": _team(team), "entry": None}
    if team is None or not user.is_authenticated:
        return {**out, "can_register": False, "can_use_pot": False}
    if not entries.can_register(user, team):
        live = entries.active_entry(t, team)
        return {
            **out,
            "entry": {**_entry(live), "stage_name": live.stage.name} if live else None,
            "can_register": False,
            "can_use_pot": False,
        }
    live = entries.active_entry(t, team)
    pays = entries._pays(user)
    return {
        **out,
        "entry": {**_entry(live), "stage_name": live.stage.name} if live else None,
        "can_register": entries.can_register(user, team),
        "can_use_pot": entries.can_use_pot(user, team),
        "pot": pot_for(team).balance,
        "wallet": wallet_for(user).balance if pays else None,
        "pays": pays,
    }


class MyEntryView(APIView):
    """GET: my team's place. POST .../register {pay_from} or .../withdraw (also declines)."""

    permission_classes = [PublicRead]
    action = None

    def get(self, request, slug):
        t = get_object_or_404(Tournament.objects.select_related("season"), slug=slug)
        return Response(my_entry_data(t, request))

    def post(self, request, slug):
        if not request.user.is_authenticated:
            raise NotAuthenticated()
        t = get_object_or_404(Tournament.objects.select_related("season"), slug=slug)
        team = _my_team(request)
        if team is None:
            raise ValidationError({"detail": "You're not on a team."})
        try:
            if self.action == "register":
                pay_from = str(request.data.get("pay_from") or Entry.PaidFrom.WALLET)
                entries.register(t, team, request.user, pay_from)
            else:
                entries.withdraw(t, team, request.user)
        except TournamentError as exc:
            _err(exc)
        return Response(my_entry_data(t, request))


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
