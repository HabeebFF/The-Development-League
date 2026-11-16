"""DC earned by playing: kills, Booyahs, match MVP and turning up.

``sync_match`` works out what every player in a match is owed and moves the difference into
(or out of) linked players' wallets. It can run any number of times: a re-upload that
changes kills pays or takes back only the difference, and a run with nothing new moves no
coins. Players without a linked account keep their DC "waiting" until they link.
"""

from __future__ import annotations

import datetime as dt
import logging

from django.conf import settings
from django.db import transaction
from django.db.models import F, Sum

from apps.league.models import Match, Player
from apps.predictions.models import LedgerEntry
from apps.predictions.services import can_play, post_entry, wallet_for
from apps.results.models import PlayerMatchResult, TeamMatchResult

from .models import DcSettings, MatchReward

log = logging.getLogger(__name__)
Kind = LedgerEntry.Kind


def enabled() -> bool:
    return bool(getattr(settings, "DC_MATCH_REWARDS", True))


def counts(match: Match, conf: DcSettings) -> bool:
    """Whether the match earns DC at all: published and on or after the start day."""
    if match.status != Match.Status.PUBLISHED:
        return False
    day = match.match_day.date if match.match_day_id else None
    return day is not None and conf.start_date is not None and day >= conf.start_date


def owed(match: Match, conf: DcSettings) -> dict[int, dict]:
    """``{player_id: {team, kills, booyah, mvp, amount}}`` for the match as it stands."""
    from apps.results.mvp import mvp_id

    if not counts(match, conf):
        return {}
    winners = set(
        TeamMatchResult.objects.filter(match=match, placement=1).values_list("team_id", flat=True)
    )
    mvp = mvp_id(match)
    out = {}
    for r in PlayerMatchResult.objects.filter(match=match):
        booyah = r.team_id in winners
        is_mvp = r.player_id == mvp
        amount = (
            conf.played
            + conf.per_kill * r.kills
            + (conf.booyah if booyah else 0)
            + (conf.mvp if is_mvp else 0)
        )
        out[r.player_id] = {
            "team_id": r.team_id,
            "kills": r.kills,
            "booyah": booyah,
            "mvp": is_mvp,
            "amount": amount,
        }
    return out


def settle(row: MatchReward) -> int:
    """Move what's still owed on ``row`` to (or from) the player's wallet. Returns the DC moved
    (negative when taken back). Unlinked players and staff accounts keep it waiting."""
    with transaction.atomic():
        row = (
            MatchReward.objects.select_for_update(of=("self",))
            .select_related("player__user", "match__match_day")
            .get(pk=row.pk)
        )
        diff = row.amount - row.paid
        user = row.player.user
        if diff == 0:
            return 0
        if diff > 0:
            if user is None or not can_play(user):
                return 0
            wallet = wallet_for(user)
            post_entry(
                wallet,
                Kind.MATCH_REWARD,
                diff,
                f"reward:{row.pk}:{row.moves + 1}",
                reason=_reason(row),
            )
            row.paid_to = user
            moved = diff
        else:
            # Taking back: from whoever was paid. Never below 0; what's left is recorded.
            target = row.paid_to
            take = 0
            if target is not None:
                wallet = wallet_for(target)
                take = min(-diff, wallet.balance)
                if take:
                    post_entry(
                        wallet,
                        Kind.MATCH_REWARD,
                        -take,
                        f"reward:{row.pk}:{row.moves + 1}",
                        reason=f"Correction: {_reason(row)}",
                    )
            row.shortfall += -diff - take
            moved = -take
        row.paid = row.amount
        row.moves += 1
        row.save(update_fields=["paid", "paid_to", "shortfall", "moves", "updated_at"])
    return moved


def _reason(row: MatchReward) -> str:
    m = row.match
    day = m.match_day
    return f"Match {m.number}, {day}: {row.breakdown()}"[:300]


def sync_match(match: Match | int, *, conf: DcSettings | None = None) -> dict:
    """Bring a match's rewards up to date and settle them. Returns a short report."""
    if not enabled():
        return {"skipped": "off"}
    conf = conf or DcSettings.get()
    if not conf.rewards_enabled:
        return {"skipped": "off"}
    match = (
        match
        if isinstance(match, Match)
        else Match.objects.select_related("match_day").filter(pk=match).first()
    )
    if match is None:
        return {"skipped": "no match"}
    want = owed(match, conf)
    rows = {r.player_id: r for r in MatchReward.objects.filter(match=match)}
    moved = 0
    for pid, w in want.items():
        row = rows.pop(pid, None)
        if row is None:
            row = MatchReward.objects.create(
                match=match,
                player_id=pid,
                team_id=w["team_id"],
                kills=w["kills"],
                booyah=w["booyah"],
                mvp=w["mvp"],
                amount=w["amount"],
            )
        elif (row.kills, row.booyah, row.mvp, row.amount, row.team_id) != (
            w["kills"],
            w["booyah"],
            w["mvp"],
            w["amount"],
            w["team_id"],
        ):
            row.kills, row.booyah, row.mvp = w["kills"], w["booyah"], w["mvp"]
            row.amount, row.team_id = w["amount"], w["team_id"]
            row.save(update_fields=["kills", "booyah", "mvp", "amount", "team_id", "updated_at"])
        moved += settle(row)
    # Players no longer in the match (or the match no longer counts): owed nothing now.
    for row in rows.values():
        if row.amount or row.kills or row.booyah or row.mvp:
            row.kills, row.booyah, row.mvp, row.amount = 0, False, False, 0
            row.save(update_fields=["kills", "booyah", "mvp", "amount", "updated_at"])
        moved += settle(row)
    return {"match": match.pk, "players": len(want), "moved": moved}


def take_back_match(match: Match) -> None:
    """Before a match is deleted: take back what it paid (its reward rows go with it)."""
    for row in MatchReward.objects.filter(match=match):
        if row.amount:
            row.amount = 0
            row.save(update_fields=["amount", "updated_at"])
        try:
            settle(row)
        except Exception:  # never block a delete over coins
            log.exception("Couldn't take back DC for reward %s", row.pk)


def pay_waiting(player: Player | int | None = None) -> int:
    """Pay out rewards still owed to linked players (all players, or one). Returns DC paid."""
    if not enabled():
        return 0
    rows = MatchReward.objects.exclude(amount=F("paid")).filter(player__user__isnull=False)
    if player is not None:
        rows = rows.filter(player=player)
    return sum(settle(r) for r in rows)


def recent_matches(days: int = 2):
    from apps.predictions.services import lagos_today

    since = lagos_today() - dt.timedelta(days=days)
    return Match.objects.filter(match_day__date__gte=since).select_related("match_day")


def sweep() -> dict:
    """Every few minutes: recent matches (ratings may have changed the MVP) and waiting DC
    for players who linked since."""
    if not enabled():
        return {"skipped": "off"}
    conf = DcSettings.get()
    synced = [sync_match(m, conf=conf) for m in recent_matches()] if conf.rewards_enabled else []
    return {"matches": len(synced), "paid_waiting": pay_waiting()}


def waiting_by_player() -> dict[int, int]:
    """DC waiting for players without a linked account: ``{player_id: dc}``."""
    rows = (
        MatchReward.objects.filter(player__user__isnull=True)
        .values("player_id")
        .annotate(total=Sum(F("amount") - F("paid")))
    )
    return {r["player_id"]: r["total"] for r in rows if r["total"] and r["total"] > 0}


def backpay_preview(since: dt.date) -> dict:
    """What lowering the start day to ``since`` would pay (nothing is changed)."""
    conf = DcSettings.get()
    if conf.start_date and since >= conf.start_date:
        return {"matches": 0, "dc": 0, "linked_dc": 0, "waiting_dc": 0}
    probe = DcSettings(
        per_kill=conf.per_kill,
        booyah=conf.booyah,
        mvp=conf.mvp,
        played=conf.played,
        start_date=since,
    )
    matches = Match.objects.filter(
        status=Match.Status.PUBLISHED,
        match_day__date__gte=since,
        match_day__date__lt=conf.start_date,
    ).select_related("match_day")
    linked = set(Player.objects.filter(user__isnull=False).values_list("pk", flat=True))
    total = linked_dc = n = 0
    for m in matches:
        n += 1
        for pid, w in owed(m, probe).items():
            total += w["amount"]
            if pid in linked:
                linked_dc += w["amount"]
    return {"matches": n, "dc": total, "linked_dc": linked_dc, "waiting_dc": total - linked_dc}


def backpay(since: dt.date, user=None) -> dict:
    """Lower the start day to ``since`` and pay the matches from then."""
    preview = backpay_preview(since)
    conf = DcSettings.get()
    if conf.start_date and since < conf.start_date:
        old = conf.start_date
        conf.start_date = since
        conf.updated_by = user
        conf.save(update_fields=["start_date", "updated_by", "updated_at"])
        for m in Match.objects.filter(
            match_day__date__gte=since, match_day__date__lt=old
        ).select_related("match_day"):
            sync_match(m, conf=conf)
    return preview


def summary_for(user) -> dict:
    """What a signed-in player earned by playing: totals and the latest matches."""
    from apps.predictions.services import lagos_today

    player = Player.objects.filter(user=user).first()
    if player is None:
        return {"linked": False}
    rows = MatchReward.objects.filter(player=player).select_related("match__match_day")
    month_start = lagos_today().replace(day=1)
    total = rows.aggregate(s=Sum("amount"))["s"] or 0
    month = rows.filter(match__match_day__date__gte=month_start).aggregate(s=Sum("amount"))["s"]
    latest = []
    for r in rows.filter(amount__gt=0).order_by("-match__match_day__date", "-match__number")[:10]:
        day = r.match.match_day
        latest.append(
            {
                "match_id": r.match_id,
                "day": str(day),
                "date": day.date if day else None,
                "number": r.match.number,
                "kills": r.kills,
                "booyah": r.booyah,
                "mvp": r.mvp,
                "amount": r.amount,
            }
        )
    waiting = sum(max(r.amount - r.paid, 0) for r in rows.exclude(amount=F("paid")))
    return {
        "linked": True,
        "player_id": player.pk,
        "total": total,
        "this_month": month or 0,
        "waiting": waiting,
        "latest": latest,
    }
