"""Multiples (accumulators): 2 to 8 picks on different markets, the odds multiplied.

The rules, all worked out here on the server:

- Every pick must be open for predictions when it is placed, at the odds it has then.
- Picks can't come from the same match: one market's result says a lot about another's
  on the same match (or a whole-session market on that session), so their odds would
  overpay. Season-long and date-range markets combine with anything.
- A losing pick loses the whole multiple, as soon as its market settles.
- A refunded pick counts as odds 1, so the others still stand; a won pick in a dead heat
  counts at its odds divided by the number tied. With every pick refunded the stake comes
  back.
- What a multiple pays is stake x the picks' odds, rounded down, and never more than
  ``PREDICTIONS_MAX_RETURN`` coins.

Each settlement of a market re-works the multiples with a pick on it, inside the same
transaction, posting the difference from what they were already paid (as single bets do).
"""

from __future__ import annotations

import uuid
from decimal import ROUND_FLOOR, Decimal
from fractions import Fraction

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .markets import (
    MarketError,
    accepting_bets,
    clean_odds,
    clean_stake,
    market_team_ids,
    own_team_ids,
)
from .models import Bet, LedgerEntry, Leg, Market, Multiple, Outcome, Settlement, Wallet
from .services import CoinError, can_play, post_entry, wallet_for

B, S, Kind = Bet.Status, Market.Status, LedgerEntry.Kind


def max_picks() -> int:
    return settings.PREDICTIONS_MAX_PICKS


def max_return() -> int:
    return settings.PREDICTIONS_MAX_RETURN


def combined_odds(odds) -> Decimal:
    """Every pick's odds multiplied, rounded down to 2 decimals (for showing only)."""
    total = Decimal(1)
    for o in odds:
        total *= Decimal(o)
    return total.quantize(Decimal("0.01"), rounding=ROUND_FLOOR)


def multiple_return(stake: int, factors) -> int:
    """stake x every factor, rounded down to a whole coin and capped. Exact: no rounding
    happens until the end, even with dead-heat factors like 2.00 / 3."""
    total = Fraction(stake)
    for f in factors:
        total *= Fraction(f)
    return min(int(total), max_return())  # int() rounds a positive fraction down


def _event(market: Market) -> tuple | None:
    """What a market is about, for spotting picks on the same match: (season, date,
    session, match number or None for the whole session). None for markets on the
    season or a range of dates."""
    f = market.fixture
    if f is None:
        return None
    return (f.season_id, f.date, f.session, f.match_number)


def clash(a: Market, b: Market) -> bool:
    """True when two markets can't be in one multiple: the same match, or a whole-session
    market and anything in that session."""
    x, y = _event(a), _event(b)
    if x is None or y is None:
        return False
    if x[:3] != y[:3]:
        return False
    return x[3] is None or y[3] is None or x[3] == y[3]


def _clean_picks(picks) -> list[dict]:
    if not isinstance(picks, list) or not 2 <= len(picks) <= max_picks():
        raise MarketError(f"A multiple needs 2 to {max_picks()} picks.", "picks")
    out = []
    for p in picks:
        try:
            out.append(
                {
                    "market": int(p["market"]),
                    "outcome": int(p["outcome"]),
                    "expected_odds": p.get("expected_odds"),
                }
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketError("Each pick needs a market and a choice.", "picks") from exc
    if len({p["market"] for p in out}) != len(out):
        raise MarketError("Only one pick per market.", "picks")
    return out


def place_multiple(user, *, picks, stake, client_key: uuid.UUID) -> tuple[Multiple, bool]:
    """Take the stake and record the multiple with its picks together, or do neither.

    Odds come from each outcome as it is when the markets are locked; odds the client
    sends are only compared. A repeat of the same ``client_key`` returns the first
    multiple without charging again. Returns ``(multiple, created)``.
    """
    if not can_play(user):
        raise MarketError("League staff can't play predictions.", "not_allowed")
    stake = clean_stake(stake)
    picks = _clean_picks(picks)
    wanted = {(p["market"], p["outcome"]) for p in picks}

    def same(m: Multiple) -> tuple[Multiple, bool]:
        got = set(m.legs.values_list("market_id", "outcome_id"))
        if got != wanted or m.stake != stake:
            raise MarketError("This confirmation was already used for another bet.", "key_reused")
        return m, False

    if existing := Multiple.objects.filter(user=user, client_key=client_key).first():
        return same(existing)

    wallet = wallet_for(user)
    mine = own_team_ids(user)
    try:
        with transaction.atomic():
            # Locked in id order, so two requests can't wait on each other.
            ids = sorted(p["market"] for p in picks)
            markets = {
                m.pk: m
                for m in Market.objects.select_for_update(of=("self",))
                .filter(pk__in=ids)
                .select_related("fixture")
                .order_by("pk")
            }
            legs = []
            for p in picks:
                market = markets.get(p["market"])
                if market is None or market.status == S.DRAFT:
                    raise MarketError("A pick's market doesn't exist.", "not_found")
                outcome = Outcome.objects.filter(pk=p["outcome"], market=market).first()
                if outcome is None:
                    raise MarketError(
                        f"That choice isn't part of {market.title}.", "outcome", market=market.pk
                    )
                if not accepting_bets(market):
                    raise MarketError(
                        f"{market.title} isn't taking predictions now.", "closed", market=market.pk
                    )
                if not outcome.is_active:
                    raise MarketError(
                        f"{outcome.label} is no longer available.", "outcome", market=market.pk
                    )
                if market_team_ids(market) & mine:
                    raise MarketError(
                        f"You can't predict on {market.title}: it's about your own team.",
                        "not_allowed",
                        market=market.pk,
                    )
                if (
                    p["expected_odds"] is not None
                    and clean_odds(p["expected_odds"]) != outcome.odds
                ):
                    raise MarketError(
                        f"The odds for {outcome.label} changed to {outcome.odds}. "
                        "Check and confirm again.",
                        "odds_changed",
                        market=market.pk,
                        outcome=outcome.pk,
                        odds=str(outcome.odds),
                    )
                legs.append((market, outcome))
            for i, (a, _) in enumerate(legs):
                for b, _ in legs[i + 1 :]:
                    if clash(a, b):
                        raise MarketError(
                            f"{a.title} and {b.title} are on the same match, so they can't "
                            "be in one multiple.",
                            "same_match",
                            markets=[a.pk, b.pk],
                        )
            odds = [o.odds for _, o in legs]
            multiple = Multiple.objects.create(
                user=user,
                stake=stake,
                odds=combined_odds(odds),
                potential_return=multiple_return(stake, odds),
                client_key=client_key,
            )
            Leg.objects.bulk_create(
                Leg(multiple=multiple, market=m, outcome=o, odds_accepted=o.odds) for m, o in legs
            )
            post_entry(
                wallet, Kind.STAKE, -stake, f"stake:multiple:{multiple.pk}", multiple=multiple
            )
    except CoinError as exc:
        raise MarketError(str(exc), "coins") from exc
    except IntegrityError:
        # The same confirmation arrived twice at once and the other one won.
        existing = Multiple.objects.filter(user=user, client_key=client_key).first()
        if existing is None:
            raise
        return same(existing)
    return multiple, True


# -- settling ------------------------------------------------------------------------------------


def outcome_of(multiple: Multiple, legs: list[Leg]) -> tuple[str, int | None]:
    """(status, payout) the picks say so far; payout is None while it's still pending."""
    statuses = [leg.status for leg in legs]
    if B.LOST in statuses:
        return B.LOST, 0
    if B.PENDING in statuses:
        return B.PENDING, None
    if all(s == B.VOID for s in statuses):
        return B.VOID, multiple.stake
    factors = [
        Fraction(leg.odds_accepted) / leg.dead_heat if leg.status == B.WON else 1 for leg in legs
    ]
    return B.WON, multiple_return(multiple.stake, factors)


def apply_legs(
    market: Market, settlement: Settlement, winners: set[int], voids: set[int], late_from
) -> dict:
    """Settle the picks on ``market`` under ``settlement`` and re-work their multiples.
    Runs inside the settlement's transaction, with the market row locked."""
    counts: dict = {}

    def add(key: str, n: int = 1) -> None:
        counts[key] = counts.get(key, 0) + n

    n = settlement.version
    now = timezone.now()
    for leg in market.legs.select_related("multiple").order_by("multiple_id"):
        # Locked in id order: two markets settling at once can't wait on each other.
        multiple = Multiple.objects.select_for_update().get(pk=leg.multiple_id)
        if settlement.kind == Settlement.Kind.VOID or leg.outcome_id in voids:
            leg.status, leg.dead_heat = B.VOID, 1
        elif late_from is not None and multiple.placed_at >= late_from:
            leg.status, leg.dead_heat = B.VOID, 1  # placed after the match really started
        elif leg.outcome_id in winners:
            leg.status, leg.dead_heat = B.WON, settlement.dead_heat
        else:
            leg.status, leg.dead_heat = B.LOST, 1
        leg.save(update_fields=["status", "dead_heat"])
        add(f"picks_{leg.status.lower()}")

        status, payout = outcome_of(multiple, list(multiple.legs.all()))
        wallet = Wallet.objects.get(user=multiple.user_id)
        before = multiple.payout or 0
        owed = payout or 0
        key = f"{multiple.pk}:{market.pk}:v{n}"
        if multiple.settled_at is None:
            if owed:
                kind = Kind.REFUND if status == B.VOID else Kind.PAYOUT
                post_entry(
                    wallet,
                    kind,
                    owed,
                    f"{kind.lower()}:multiple:{key}",
                    multiple=multiple,
                    settlement=settlement,
                )
                add("multiple_coins_paid", owed)
        elif owed > before:
            # Coins a previous correction couldn't take back are never paid out again.
            offset = min(owed - before, multiple.unrecovered)
            multiple.unrecovered -= offset
            if owed - before - offset:
                post_entry(
                    wallet,
                    Kind.CORRECTION,
                    owed - before - offset,
                    f"correction:multiple:{key}",
                    multiple=multiple,
                    settlement=settlement,
                    reason=settlement.reason,
                )
            add("multiple_coins_paid", owed - before - offset)
        elif owed < before:
            wallet.refresh_from_db()
            take = min(before - owed, wallet.balance)
            if take:
                post_entry(
                    wallet,
                    Kind.CORRECTION,
                    -take,
                    f"correction:multiple:{key}",
                    multiple=multiple,
                    settlement=settlement,
                    reason=settlement.reason,
                )
            add("multiple_coins_taken", take)
            if take < before - owed:
                multiple.unrecovered += before - owed - take
                add("multiple_coins_unrecovered", before - owed - take)
        multiple.status, multiple.payout = status, payout
        multiple.settled_at = None if status == B.PENDING else now
        multiple.save(update_fields=["status", "payout", "settled_at", "unrecovered"])
        add(f"multiples_{status.lower()}")
    return counts
