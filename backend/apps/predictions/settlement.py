"""Settling, voiding and correcting markets.

Staff confirm every result. The site suggests one from the published match (the evidence),
and staff must give a reason to settle any other way. Each decision is a new ``Settlement``
version; coins move through ``post_entry`` with keys that include the version, so repeating
a request never pays, refunds or corrects twice.
"""

from __future__ import annotations

from collections import Counter

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.league.models import Match
from apps.results.models import TeamMatchResult

from .markets import H2H, MarketError
from .models import Bet, Market, MarketEvent, Outcome, Settlement, Wallet
from .services import Kind, post_entry

C = Market.Category
S = Market.Status
B = Bet.Status


# -- the suggested result ------------------------------------------------------------------------


def linked_match(market: Market) -> Match:
    """The published match a match-level market is about; raises ``MarketError`` if not ready."""
    fixture = market.fixture
    if fixture is None or fixture.match_number is None:
        raise MarketError("This market isn't about one match.", "not_ready")
    if fixture.match_id is None:
        raise MarketError("Link the fixture to its uploaded match first.", "not_ready")
    match = fixture.match
    if match.status != Match.Status.PUBLISHED:
        raise MarketError("The match isn't published yet.", "not_ready")
    return match


def suggest(market: Market) -> dict:
    """What the published match says the result is.

    Returns ``{"kind", "winners": [outcome ids], "voids": [outcome ids], "note", "evidence"}``.
    """
    match = linked_match(market)
    outcomes = list(market.outcomes.all())
    rows = {
        r.team_id: r for r in TeamMatchResult.objects.filter(match=match).select_related("team")
    }
    evidence = {
        "match": match.pk,
        "match_title": str(match),
        "started_at": match.started_at.isoformat() if match.started_at else None,
        "teams_in_lobby": len(rows),
        "results": [
            {
                "team": r.team_id,
                "name": r.team.name,
                "placement": r.placement,
                "kills": r.kills,
                "points": r.total_points,
            }
            for r in sorted(rows.values(), key=lambda r: r.placement)
            if r.team_id in _teams(market)
        ],
    }
    if not rows:
        raise MarketError("The match has no results.", "not_ready")

    def by_team(team_id: int) -> Outcome:
        return next(o for o in outcomes if o.team_id == team_id)

    def void(note: str) -> dict:
        return {"kind": "VOID", "winners": [], "voids": [], "note": note, "evidence": evidence}

    def settle(winners, voids=(), note="") -> dict:
        return {
            "kind": "SETTLE",
            "winners": [o.pk for o in winners],
            "voids": [o.pk for o in voids],
            "note": note,
            "evidence": evidence,
        }

    if market.category == C.BOOYAH:
        absent = [o for o in outcomes if o.team_id not in rows]
        first = next((r for r in rows.values() if r.placement == 1), None)
        winners = [by_team(first.team_id)] if first and first.team_id in _teams(market) else []
        note = "" if winners else "The Booyah team isn't one of the choices: every bet loses."
        if absent:
            note = (note + " " if note else "") + "Teams that didn't play are refunded."
        return settle(winners, absent, note.strip())

    if market.category == C.TOP_N:
        row = rows.get(market.params["team"])
        if row is None:
            return void("The team didn't play: everyone is refunded.")
        code = "yes" if row.placement <= market.params["n"] else "no"
        return settle([next(o for o in outcomes if o.code == code)])

    if market.category in H2H:
        a, b = market.params["teams"]
        if a not in rows or b not in rows:
            return void("One of the teams didn't play: everyone is refunded.")
        if market.category == C.H2H_PLACEMENT:
            winner = a if rows[a].placement < rows[b].placement else b
        else:
            field = "kills" if market.category == C.H2H_KILLS else "total_points"
            va, vb = getattr(rows[a], field), getattr(rows[b], field)
            if va == vb:
                return void("A tie: everyone is refunded.")
            winner = a if va > vb else b
        return settle([by_team(winner)])

    raise MarketError("No automatic result for this kind of market.", "not_ready")


def _teams(market: Market) -> set[int]:
    p = market.params or {}
    return set(p.get("teams") or []) | ({p["team"]} if p.get("team") else set())


# -- applying a decision -------------------------------------------------------------------------


def _target(bet: Bet, kind: str, winners: set[int], voids: set[int], late_from) -> tuple[str, int]:
    """(status, payout) this bet ends up with under a decision."""
    if kind == Settlement.Kind.VOID or bet.outcome_id in voids:
        return B.VOID, bet.stake
    if late_from is not None and bet.placed_at >= late_from:
        return B.VOID, bet.stake  # placed after the match really started
    if bet.outcome_id in winners:
        return B.WON, bet.potential_return
    return B.LOST, 0


def _apply(market: Market, settlement: Settlement, late_from) -> dict:
    winners = set(settlement.winning_outcomes.values_list("pk", flat=True))
    voids = set(settlement.void_outcomes.values_list("pk", flat=True))
    n = settlement.version
    now = timezone.now()
    counts: Counter = Counter()
    for bet in market.bets.select_related("user").order_by("placed_at", "pk"):
        status, payout = _target(bet, settlement.kind, winners, voids, late_from)
        wallet = Wallet.objects.get(user=bet.user)
        if bet.status == B.PENDING:
            if payout:
                kind = Kind.REFUND if status == B.VOID else Kind.PAYOUT
                prefix = "refund" if status == B.VOID else "payout"
                post_entry(
                    wallet, kind, payout, f"{prefix}:{bet.pk}:v{n}", bet=bet, settlement=settlement
                )
            counts["coins_paid"] += payout
        else:
            delta = payout - (bet.payout or 0)
            if delta > 0:
                # Coins a previous correction couldn't take back are never paid out again.
                offset = min(delta, bet.unrecovered)
                bet.unrecovered -= offset
                if delta - offset:
                    post_entry(
                        wallet,
                        Kind.CORRECTION,
                        delta - offset,
                        f"correction:{bet.pk}:v{n}",
                        bet=bet,
                        settlement=settlement,
                        reason=settlement.reason,
                    )
                counts["coins_paid"] += delta - offset
            elif delta < 0:
                wallet.refresh_from_db()
                take = min(-delta, wallet.balance)
                if take:
                    post_entry(
                        wallet,
                        Kind.CORRECTION,
                        -take,
                        f"correction:{bet.pk}:v{n}",
                        bet=bet,
                        settlement=settlement,
                        reason=settlement.reason,
                    )
                counts["coins_taken"] += take
                if take < -delta:
                    bet.unrecovered += -delta - take
                    counts["coins_unrecovered"] += -delta - take
        counts[status.lower()] += 1
        bet.status, bet.payout, bet.settled_at = status, payout, now
        bet.save(update_fields=["status", "payout", "settled_at", "unrecovered"])
    return dict(counts)


def _decide(
    market_id: int,
    *,
    kind: str,
    actor,
    winners=(),
    voids=(),
    reference: str = "",
    reason: str = "",
    allowed_from: set[str],
    evidence: dict | None = None,
    request_key: str | None = None,
) -> tuple[Settlement, bool]:
    with transaction.atomic():
        market = Market.objects.select_for_update().get(pk=market_id)
        latest = market.settlements.order_by("-version").first()
        if market.status not in allowed_from:
            raise MarketError(
                f"A {market.status.lower()} market can't be changed this way.", "wrong_status"
            )
        outcome_ids = set(market.outcomes.values_list("pk", flat=True))
        winners, voids = set(winners), set(voids)
        if not (winners | voids) <= outcome_ids:
            raise MarketError("A chosen outcome isn't part of this market.", "outcome")
        if winners & voids:
            raise MarketError("An outcome can't both win and be refunded.", "outcome")
        if kind == Settlement.Kind.SETTLE and not winners and not voids:
            raise MarketError("Pick the winning outcome.", "outcome")
        late_from = None
        if market.fixture and market.fixture.match_number and market.fixture.match_id:
            late_from = market.fixture.match.started_at
        settlement = Settlement.objects.create(
            market=market,
            version=(latest.version + 1) if latest else 1,
            kind=kind,
            evidence=evidence or {},
            reference=reference,
            reason=reason,
            actor=actor,
            supersedes=latest,
            request_key=request_key,
        )
        settlement.winning_outcomes.set(winners)
        settlement.void_outcomes.set(voids)
        settlement.summary = _apply(market, settlement, late_from)
        settlement.save(update_fields=["summary"])
        to = S.VOID if kind == Settlement.Kind.VOID else S.SETTLED
        MarketEvent.objects.create(
            market=market,
            from_status=market.status,
            to_status=to,
            actor=actor,
            reason=reason or f"Settlement v{settlement.version}",
        )
        market.status = to
        market.updated_by = actor
        market.save(update_fields=["status", "updated_by", "updated_at"])
    return settlement, True


def settle(
    market: Market, *, actor, winners, voids=(), reference: str = "", override_reason: str = ""
) -> tuple[Settlement, bool]:
    """Settle a CLOSED market (first time). Repeating the same request changes nothing."""
    market.refresh_from_db()
    if market.status == S.VOID:
        raise MarketError("This market was voided. Use a correction to settle it.", "wrong_status")
    if market.status == S.SETTLED:
        latest = market.settlements.order_by("-version").first()
        if (
            latest.version == 1
            and set(latest.winning_outcomes.values_list("pk", flat=True)) == set(winners)
            and set(latest.void_outcomes.values_list("pk", flat=True)) == set(voids)
        ):
            return latest, False
        raise MarketError("Already settled. Use a correction to change it.", "already_settled")
    suggestion = suggest(market)  # raises when the match isn't ready
    matches = (
        suggestion["kind"] == "SETTLE"
        and set(suggestion["winners"]) == set(winners)
        and set(suggestion["voids"]) == set(voids)
    )
    if not matches and not override_reason.strip():
        raise MarketError(
            "That isn't what the match result says. Give a reason to override it.", "override"
        )
    try:
        return _decide(
            market.pk,
            kind=Settlement.Kind.SETTLE,
            actor=actor,
            winners=winners,
            voids=voids,
            reference=reference,
            reason=override_reason.strip(),
            allowed_from={S.CLOSED},
            evidence=suggestion["evidence"],
        )
    except MarketError as exc:
        if exc.code != "wrong_status":
            raise
        # Another request settled it a moment ago: same answer, same result.
        return settle(market, actor=actor, winners=winners, voids=voids)


def void(market: Market, *, actor, reason: str, reference: str = "") -> tuple[Settlement, bool]:
    """Refund every bet once. Voiding a void market again changes nothing."""
    if not reason.strip():
        raise MarketError("Give a reason for voiding.", "reason")
    market.refresh_from_db()
    if market.status == S.VOID:
        return market.settlements.order_by("-version").first(), False
    if market.status == S.SETTLED:
        raise MarketError("Already settled. Use a correction to void it.", "already_settled")
    try:
        return _decide(
            market.pk,
            kind=Settlement.Kind.VOID,
            actor=actor,
            reference=reference,
            reason=reason.strip(),
            allowed_from={S.DRAFT, S.OPEN, S.SUSPENDED, S.CLOSED},
        )
    except MarketError as exc:
        if exc.code != "wrong_status":
            raise
        return void(market, actor=actor, reason=reason)


def correct(
    market: Market,
    *,
    actor,
    kind: str,
    reason: str,
    winners=(),
    voids=(),
    reference: str = "",
    key: str = "",
) -> tuple[Settlement, bool]:
    """Replace a settled or voided result with a new version.

    Each bet gets one CORRECTION entry for the difference between what it was owed and
    what it is owed now. If a player has already spent coins being taken back, their
    balance stops at 0 and the rest is recorded on the bet as ``unrecovered``.
    ``key`` (from the staff form) makes a resend of the same correction do nothing.
    """
    if not reason.strip():
        raise MarketError("Give a reason for the correction.", "reason")
    market.refresh_from_db()
    request_key = f"correct:{market.pk}:{key}" if key else None
    if request_key and (done := Settlement.objects.filter(request_key=request_key).first()):
        return done, False
    if market.status not in (S.SETTLED, S.VOID) or not market.settlements.exists():
        raise MarketError("Only a settled or voided market can be corrected.", "wrong_status")
    evidence = {}
    try:
        evidence = suggest(market)["evidence"]
    except MarketError:
        pass  # a void correction may not have a published match
    try:
        return _decide(
            market.pk,
            kind=kind,
            actor=actor,
            winners=winners if kind == Settlement.Kind.SETTLE else (),
            voids=voids if kind == Settlement.Kind.SETTLE else (),
            reference=reference,
            reason=reason.strip(),
            allowed_from={S.SETTLED, S.VOID},
            evidence=evidence,
            request_key=request_key,
        )
    except IntegrityError:
        # The same correction was sent twice at once and the other one won.
        done = Settlement.objects.filter(request_key=request_key).first() if request_key else None
        if done is None:
            raise
        return done, False


def settlement_data(s: Settlement) -> dict:
    return {
        "id": s.pk,
        "version": s.version,
        "kind": s.kind,
        "winners": list(s.winning_outcomes.values("id", "label")),
        "voids": list(s.void_outcomes.values("id", "label")),
        "evidence": s.evidence,
        "reference": s.reference,
        "reason": s.reason,
        "summary": s.summary,
        "by": s.actor.email,
        "supersedes": s.supersedes.version if s.supersedes else None,
        "created_at": s.created_at,
    }
