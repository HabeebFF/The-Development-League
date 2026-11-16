"""DC ranks, the team DC table and the monthly DC King.

"Earned" DC is everything a wallet gained from playing, predicting and bonuses: every ledger
entry except the starting coins and shop buys/refunds. Spending in a shop never lowers a rank.
Players without an account are ranked on the DC waiting for them from their matches.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError
from django.db.models import F, Q, Sum

from apps.league.models import Player
from apps.predictions.models import LedgerEntry

from .models import DcSettings, MatchReward, Spotlight

Kind = LedgerEntry.Kind
# Not "earned": the starting coins, and coins moved in and out of the shops.
NOT_EARNED = [
    Kind.INITIAL,
    Kind.PURCHASE,
    Kind.SHOP_REFUND,
    Kind.PERK,
    Kind.PERK_REFUND,
    Kind.TEAM_POT,
]


def _tz():
    return ZoneInfo(settings.ANALYTICS_TIME_ZONE)


def month_start(day: dt.date) -> dt.date:
    return day.replace(day=1)


def next_month(day: dt.date) -> dt.date:
    return (day.replace(day=28) + dt.timedelta(days=4)).replace(day=1)


def _bounds(month: dt.date) -> tuple[dt.datetime, dt.datetime]:
    """The month as aware datetimes, Lagos time."""
    tz = _tz()
    start = dt.datetime.combine(month, dt.time(), tzinfo=tz)
    return start, dt.datetime.combine(next_month(month), dt.time(), tzinfo=tz)


def rank_for(earned: int, steps: list[dict]) -> dict | None:
    """The highest step ``earned`` reaches, or None (Rookie)."""
    best = None
    for step in sorted(steps, key=lambda s: s["min"]):
        if earned >= step["min"]:
            best = step
    return best


def _earned_entries():
    return LedgerEntry.objects.exclude(kind__in=NOT_EARNED).filter(wallet__user__is_active=True)


def earned_by_user(since: dt.datetime | None = None, until: dt.datetime | None = None):
    """``{user_id: dc}``, never below 0."""
    rows = _earned_entries()
    if since:
        rows = rows.filter(created_at__gte=since)
    if until:
        rows = rows.filter(created_at__lt=until)
    totals = rows.values("wallet__user_id").annotate(total=Sum("amount"))
    return {r["wallet__user_id"]: max(r["total"] or 0, 0) for r in totals}


def player_earned() -> dict[int, int]:
    """``{player_id: earned DC}`` for every player with any: linked players from their wallet,
    the rest from the DC waiting for them. Staff accounts are left out."""
    by_user = earned_by_user()
    out: dict[int, int] = {}
    linked = Player.objects.filter(user__isnull=False).values_list("pk", "user_id")
    staff = _staff_ids()
    for pid, uid in linked:
        if uid in staff:
            continue
        if by_user.get(uid):
            out[pid] = by_user[uid]
    waiting = (
        MatchReward.objects.filter(player__user__isnull=True)
        .values("player_id")
        .annotate(total=Sum(F("amount") - F("paid")))
    )
    for r in waiting:
        if r["total"] and r["total"] > 0:
            out[r["player_id"]] = r["total"]
    return out


def _staff_ids() -> set[int]:
    from apps.accounts.models import StaffProfile, User

    ids = set(StaffProfile.objects.values_list("user_id", flat=True))
    ids |= set(
        User.objects.filter(Q(is_staff=True) | Q(is_superuser=True)).values_list("pk", flat=True)
    )
    return ids


def team_month(month: dt.date, limit: int | None = None) -> list[dict]:
    """Teams by DC their players earned from matches in ``month`` (Lagos)."""
    rows = (
        MatchReward.objects.filter(
            match__match_day__date__gte=month,
            match__match_day__date__lt=next_month(month),
            team__isnull=False,
            amount__gt=0,
        )
        .values("team_id", "team__name", "team__slug")
        .annotate(dc=Sum("amount"))
        .order_by("-dc", "team__name")
    )
    out = [
        {"team_id": r["team_id"], "name": r["team__name"], "slug": r["team__slug"], "dc": r["dc"]}
        for r in rows
    ]
    return out[:limit] if limit else out


def month_leaders(month: dt.date) -> list[tuple[int, int, int]]:
    """``[(player_id, earned, from_matches)]`` for linked league players in ``month``, best
    first. Ties go to more DC from matches, then the lower player id."""
    start, end = _bounds(month)
    by_user = earned_by_user(start, end)
    staff = _staff_ids()
    matches = dict(
        MatchReward.objects.filter(
            match__match_day__date__gte=month, match__match_day__date__lt=next_month(month)
        )
        .values("player_id")
        .annotate(t=Sum("amount"))
        .values_list("player_id", "t")
    )
    rows = []
    for pid, uid in Player.objects.filter(user__isnull=False).values_list("pk", "user_id"):
        if uid in staff or not by_user.get(uid):
            continue
        rows.append((pid, by_user[uid], matches.get(pid) or 0))
    rows.sort(key=lambda r: (-r[1], -r[2], r[0]))
    return rows


def crown(month: dt.date) -> Spotlight | None:
    """Make ``month``'s DC King (once). Returns the spotlight, or None if nobody earned DC."""
    month = month_start(month)
    existing = Spotlight.objects.filter(month=month).first()
    if existing:
        return existing
    leaders = month_leaders(month)
    if not leaders:
        return None
    pid, earned, from_matches = leaders[0]
    try:
        spot = Spotlight.objects.create(
            month=month, player_id=pid, earned=earned, from_matches=from_matches
        )
    except IntegrityError:
        return Spotlight.objects.get(month=month)
    # The "DC King" card title is theirs to keep (a Player shop milestone).
    from apps.shop.milestones import grant

    player = spot.player
    if player.user_id:
        grant(player.user, player)
    return spot


def crown_last_month(today: dt.date | None = None) -> Spotlight | None:
    from apps.predictions.services import lagos_today

    today = today or lagos_today()
    last = month_start(month_start(today) - dt.timedelta(days=1))
    return crown(last)


def current_spotlight(today: dt.date | None = None) -> Spotlight | None:
    """Last month's DC King, shown all this month (unless staff hid it)."""
    from apps.predictions.services import lagos_today

    today = today or lagos_today()
    last = month_start(month_start(today) - dt.timedelta(days=1))
    return (
        Spotlight.objects.filter(month=last, hidden=False)
        .select_related("player__current_team")
        .first()
    )


def spotlight_data(s: Spotlight | None) -> dict | None:
    if s is None:
        return None
    p = s.player
    team = p.current_team
    photo = p.photo_cutout or p.photo
    return {
        "month": s.month,
        "player_id": p.pk,
        "name": p.display_name,
        "photo": photo.url if photo else None,
        "team": {"name": team.name, "slug": team.slug} if team else None,
        "earned": s.earned,
        "from_matches": s.from_matches,
    }


def week_start(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def priority_team(day: dt.date) -> dict | None:
    """The team whose players earned the most DC from matches in the week (Mon-Sun) before
    ``day``'s week: it goes first when a scrim waitlist moves up that week. Earned, not bought,
    and it never pushes a team out of a place it already has."""
    this_week = week_start(day)
    last_week = this_week - dt.timedelta(days=7)
    row = (
        MatchReward.objects.filter(
            match__match_day__date__gte=last_week,
            match__match_day__date__lt=this_week,
            team__isnull=False,
            amount__gt=0,
        )
        .values("team_id", "team__name", "team__slug")
        .annotate(dc=Sum("amount"))
        .order_by("-dc", "team__name")
        .first()
    )
    if not row:
        return None
    return {
        "team_id": row["team_id"],
        "name": row["team__name"],
        "slug": row["team__slug"],
        "dc": row["dc"],
        "week_of": this_week,
    }


def wildcard(before: dt.date, exclude: set[int]) -> dict | None:
    """The Cup's DC wildcard: the team (not already in) whose players earned the most DC from
    matches in the 30 days before ``before``."""
    rows = (
        MatchReward.objects.filter(
            match__match_day__date__gte=before - dt.timedelta(days=30),
            match__match_day__date__lt=before,
            team__isnull=False,
            amount__gt=0,
        )
        .exclude(team_id__in=exclude)
        .values("team_id", "team__name")
        .annotate(dc=Sum("amount"))
        .order_by("-dc", "team__name")
    )
    row = rows.first()
    return {"team_id": row["team_id"], "name": row["team__name"], "dc": row["dc"]} if row else None


def board() -> dict:
    """Everything the badges need, in one cached response."""
    from apps.predictions.services import lagos_today

    conf = DcSettings.get()
    month = month_start(lagos_today())
    return {
        "steps": sorted(conf.rank_steps, key=lambda s: s["min"]),
        "initial": settings.PREDICTIONS_INITIAL_COINS,
        "players": {str(k): v for k, v in player_earned().items()},
        "teams": team_month(month),
        "king": spotlight_data(current_spotlight()),
        "priority": priority_team(lagos_today()),
    }
