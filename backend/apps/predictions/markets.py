"""Markets: what each kind of market offers, its status rules, odds changes and placing bets."""

from __future__ import annotations

import uuid
from decimal import ROUND_FLOOR, Decimal, InvalidOperation

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.league.models import Player, Team

from .models import MAX_ODDS, MIN_ODDS, Bet, Market, MarketEvent, OddsChange, Outcome
from .services import CoinError, Kind, can_play, post_entry, wallet_for

C = Market.Category
S = Market.Status

# Which status can follow which. SETTLED and VOID are reached through settlement (step 3),
# CLOSED -> OPEN only when nothing has been settled and the window is moved later.
TRANSITIONS: dict[str, set[str]] = {
    S.DRAFT: {S.OPEN, S.VOID},
    S.OPEN: {S.SUSPENDED, S.CLOSED, S.VOID},
    S.SUSPENDED: {S.OPEN, S.CLOSED, S.VOID},
    S.CLOSED: {S.OPEN, S.SETTLED, S.VOID},
    S.SETTLED: set(),  # changed only by a correction
    S.VOID: set(),
}
EDITABLE_ODDS = {S.DRAFT, S.OPEN, S.SUSPENDED}
H2H = {C.H2H_PLACEMENT, C.H2H_KILLS, C.H2H_POINTS}
HANDICAPS = {C.KILLS_HANDICAP, C.POINTS_HANDICAP}
PLAYER_MARKETS = {C.PLAYER_KILLS, C.TOP_FRAGGER, C.PLAYER_H2H, C.FIRST_DEATH, C.PLAYER_DAMAGE}
# Phase C match markets: these can only be about one match, so they need a one-match fixture.
NEEDS_MATCH = {
    C.TEAM_KILLS,
    C.TOTAL_KILLS,
    *HANDICAPS,
    C.FINISH_BAND,
    C.FIRST_OUT,
    C.FIRST_BLOOD,
    *PLAYER_MARKETS,
}
# What a market's fixture must be: one match, a whole session, or none (season-long).
MATCH_MARKETS = {C.BOOYAH, C.TOP_N, *H2H, *NEEDS_MATCH}
SESSION_MARKETS = {C.SESSION_WINNER, C.MOST_BOOYAHS}
SEASON_MARKETS = {C.OVERALL_WINNER, C.OVERALL_TOP_N}
# Markets with one choice per team or player, where those level on the result share the win.
DEAD_HEAT = {C.SESSION_WINNER, C.MOST_BOOYAHS, C.OVERALL_WINNER, C.TOP_FRAGGER, C.FIRST_DEATH}
MAX_KILLS_LINE = 60
# Lines: (lowest, highest) for each kind of over/under or handicap.
LINES = {
    C.TEAM_KILLS: (1, MAX_KILLS_LINE),
    C.TOTAL_KILLS: (1, 300),
    C.KILLS_HANDICAP: (1, 30),
    C.POINTS_HANDICAP: (1, 100),
    C.PLAYER_KILLS: (1, 30),
    C.PLAYER_DAMAGE: (100, 20000),
}
# Finishing bands: code -> (best place, worst place).
BANDS = {"band:1": (1, 1), "band:2": (2, 3), "band:4": (4, 6), "band:7": (7, 99)}
BAND_LABELS = {"band:1": "1st", "band:2": "2nd-3rd", "band:4": "4th-6th", "band:7": "7th or lower"}


class MarketError(Exception):
    """A request about a market that was refused; ``str()`` is safe to show."""

    def __init__(self, message: str, code: str = "invalid", **extra):
        super().__init__(message)
        self.code = code
        self.extra = extra


# -- what a market offers ------------------------------------------------------------------------


def clean_params(category: str, params: dict) -> dict:
    """Check and normalise a market's params; raises ``MarketError``."""
    params = params or {}

    def team_ids(value, at_least: int, exactly: int | None = None) -> list[int]:
        if not isinstance(value, list) or not all(isinstance(t, int) for t in value):
            raise MarketError("teams must be a list of team ids.")
        ids = list(dict.fromkeys(value))
        if len(ids) != len(value):
            raise MarketError("A team is listed twice.")
        if exactly is not None and len(ids) != exactly:
            raise MarketError(f"Pick exactly {exactly} teams.")
        if len(ids) < at_least:
            raise MarketError(f"Pick at least {at_least} teams.")
        found = set(Team.objects.filter(pk__in=ids).values_list("pk", flat=True))
        if missing := [t for t in ids if t not in found]:
            raise MarketError(f"Unknown team id(s): {missing}.")
        return ids

    if category == C.BOOYAH:
        return {"teams": team_ids(params.get("teams"), at_least=2)}
    if category == C.TOP_N:
        n = params.get("n")
        if n not in (3, 5, 10):
            raise MarketError("N must be 3, 5 or 10.")
        team = team_ids([params.get("team")] if params.get("team") else [], 1, 1)[0]
        return {"team": team, "n": n}
    if category in H2H:
        return {"teams": team_ids(params.get("teams"), at_least=2, exactly=2)}

    def player_ids(value, at_least: int, exactly: int | None = None) -> list[int]:
        if not isinstance(value, list) or not all(isinstance(p, int) for p in value):
            raise MarketError("players must be a list of player ids.")
        ids = list(dict.fromkeys(value))
        if len(ids) != len(value):
            raise MarketError("A player is listed twice.")
        if exactly is not None and len(ids) != exactly:
            raise MarketError(f"Pick exactly {exactly} players.")
        if len(ids) < at_least:
            raise MarketError(f"Pick at least {at_least} players.")
        found = set(Player.objects.filter(pk__in=ids).values_list("pk", flat=True))
        if missing := [p for p in ids if p not in found]:
            raise MarketError(f"Unknown player id(s): {missing}.")
        return ids

    def line() -> int:
        lo, hi = LINES[category]
        value = params.get("line")
        if not isinstance(value, int) or isinstance(value, bool) or not lo <= value <= hi:
            what = {C.PLAYER_DAMAGE: "damage line", **dict.fromkeys(HANDICAPS, "handicap")}
            name = what.get(category, "kills line")
            raise MarketError(f"The {name} must be a whole number from {lo} to {hi}.")
        return value

    def one_team() -> int:
        return team_ids([params.get("team")] if params.get("team") else [], 1, 1)[0]

    def one_player() -> int:
        return player_ids([params.get("player")] if params.get("player") else [], 1, 1)[0]

    if category == C.TEAM_KILLS:
        return {"team": one_team(), "line": line()}
    if category == C.TOTAL_KILLS:
        return {"line": line()}
    if category in HANDICAPS:
        return {"teams": team_ids(params.get("teams"), at_least=2, exactly=2), "line": line()}
    if category == C.FINISH_BAND:
        return {"team": one_team()}
    if category in (C.FIRST_OUT, C.FIRST_BLOOD):
        return {"teams": team_ids(params.get("teams"), at_least=2)}
    if category in (C.PLAYER_KILLS, C.PLAYER_DAMAGE):
        return {"player": one_player(), "line": line()}
    if category in (C.TOP_FRAGGER, C.FIRST_DEATH):
        return {"players": player_ids(params.get("players"), at_least=2)}
    if category == C.PLAYER_H2H:
        return {"players": player_ids(params.get("players"), at_least=2, exactly=2)}
    if category in (C.SESSION_WINNER, C.MOST_BOOYAHS, C.OVERALL_WINNER):
        return {"teams": team_ids(params.get("teams"), at_least=2)}
    if category == C.OVERALL_TOP_N:
        n = params.get("n")
        if n not in (3, 5, 10):
            raise MarketError("N must be 3, 5 or 10.")
        team = team_ids([params.get("team")] if params.get("team") else [], 1, 1)[0]
        return {"team": team, "n": n}
    raise MarketError("Unknown market category.")


def check_fixture(category: str, fixture) -> None:
    """A match market needs a one-match fixture, a session market a whole-session fixture,
    and a season market no fixture."""
    if category in SEASON_MARKETS:
        if fixture is not None:
            raise MarketError("Overall markets cover the whole season: leave the fixture empty.")
        return
    if category in SESSION_MARKETS and (fixture is None or fixture.match_number is not None):
        raise MarketError("Session markets need a whole-session fixture (no match number).")
    if category in NEEDS_MATCH and (fixture is None or fixture.match_number is None):
        raise MarketError("This market needs a fixture for one match.")


def outcome_specs(category: str, params: dict) -> list[dict]:
    """The outcomes a market has: ``[{code, label, team_id}]``, in display order."""
    if category in (C.TOP_N, C.OVERALL_TOP_N):
        team = Team.objects.get(pk=params["team"])
        return [
            {"code": "yes", "label": f"Yes, {team.name} top {params['n']}", "team_id": None},
            {"code": "no", "label": f"No, {team.name} outside top {params['n']}", "team_id": None},
        ]
    if category == C.TEAM_KILLS:
        team, line = Team.objects.get(pk=params["team"]), params["line"]
        return [
            {"code": "yes", "label": f"{team.name}: {line} or more kills", "team_id": None},
            {"code": "no", "label": f"{team.name}: {line - 1} or fewer kills", "team_id": None},
        ]
    if category == C.TOTAL_KILLS:
        line = params["line"]
        return [
            {"code": "yes", "label": f"Over {line - 0.5:g} kills", "team_id": None},
            {"code": "no", "label": f"Under {line - 0.5:g} kills", "team_id": None},
        ]
    if category in HANDICAPS:
        teams = Team.objects.in_bulk(params["teams"])
        (a, b), start = params["teams"], params["line"] - 0.5
        what = "kills" if category == C.KILLS_HANDICAP else "points"
        return [
            {"code": f"team:{a}", "label": f"{teams[a].name} -{start:g} {what}", "team_id": a},
            {"code": f"team:{b}", "label": f"{teams[b].name} +{start:g} {what}", "team_id": b},
        ]
    if category == C.FINISH_BAND:
        name = Team.objects.get(pk=params["team"]).name
        return [{"code": c, "label": f"{name}: {BAND_LABELS[c]}", "team_id": None} for c in BANDS]
    if category in (C.PLAYER_KILLS, C.PLAYER_DAMAGE):
        player, line = Player.objects.get(pk=params["player"]), params["line"]
        what = "kills" if category == C.PLAYER_KILLS else "damage"
        return [
            {"code": "yes", "label": f"{player.display_name}: over {line - 0.5:g} {what}",
             "team_id": None, "player_id": player.pk},
            {"code": "no", "label": f"{player.display_name}: under {line - 0.5:g} {what}",
             "team_id": None, "player_id": player.pk},
        ]  # fmt: skip
    if category in PLAYER_MARKETS:
        players = Player.objects.in_bulk(params["players"])
        return [
            {"code": f"player:{p}", "label": players[p].display_name, "team_id": None,
             "player_id": p}
            for p in params["players"]
        ]  # fmt: skip
    teams = Team.objects.in_bulk(params["teams"])
    return [{"code": f"team:{t}", "label": teams[t].name, "team_id": t} for t in params["teams"]]


def market_team_ids(market: Market) -> set[int]:
    """Teams a market is about, including the current teams of the players it is about."""
    p = market.params or {}
    players = list(p.get("players") or []) + ([p["player"]] if p.get("player") else [])
    teams = set(
        Player.objects.filter(pk__in=players, current_team__isnull=False).values_list(
            "current_team_id", flat=True
        )
    )
    return teams | set(p.get("teams") or []) | ({p["team"]} if p.get("team") else set())


def clean_odds(value) -> Decimal:
    try:
        odds = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise MarketError("Odds must be a number like 2.50.") from exc
    if not odds.is_finite() or odds != odds.quantize(Decimal("0.01")):
        raise MarketError("Odds can have at most 2 decimal places.")
    if odds < MIN_ODDS or odds > MAX_ODDS:
        raise MarketError(f"Odds must be between {MIN_ODDS} and {MAX_ODDS}.")
    return odds


def potential_return(stake: int, odds: Decimal) -> int:
    """Stake x odds, rounded down to a whole coin. The only place this is worked out."""
    return int((Decimal(stake) * odds).to_integral_value(rounding=ROUND_FLOOR))


def dead_heat_return(stake: int, odds: Decimal, tied: int) -> int:
    """What a winning bet pays when ``tied`` teams share the win: stake x odds / tied,
    rounded down. With no tie it is the normal return."""
    if tied <= 1:
        return potential_return(stake, odds)
    return int((Decimal(stake) * odds / tied).to_integral_value(rounding=ROUND_FLOOR))


@transaction.atomic
def create_market(*, actor, category: str, odds: dict, **fields) -> Market:
    params = clean_params(category, fields.pop("params", {}))
    check_fixture(category, fields.get("fixture"))
    specs = outcome_specs(category, params)
    codes = {s["code"] for s in specs}
    if set(odds or {}) != codes:
        raise MarketError(f"Give odds for exactly these outcomes: {sorted(codes)}.")
    market = Market.objects.create(
        category=category, params=params, created_by=actor, updated_by=actor, **fields
    )
    for n, spec in enumerate(specs):
        Outcome.objects.create(
            market=market,
            code=spec["code"],
            label=spec["label"],
            team_id=spec["team_id"],
            player_id=spec.get("player_id"),
            odds=clean_odds(odds[spec["code"]]),
            sort=n,
        )
    MarketEvent.objects.create(market=market, to_status=market.status, actor=actor)
    return market


# -- status and odds -----------------------------------------------------------------------------


def transition(market: Market, to: str, *, actor, reason: str = "") -> Market:
    """Move a market to ``to`` if the rules allow it (see ``TRANSITIONS``)."""
    with transaction.atomic():
        market = Market.objects.select_for_update().get(pk=market.pk)
        if to not in TRANSITIONS.get(market.status, set()):
            raise MarketError(f"A {market.status.lower()} market can't become {to.lower()}.")
        if to in (S.SETTLED, S.VOID):
            raise MarketError("Use settle or void for that.")
        now = timezone.now()
        if to == S.OPEN:
            if market.closes_at <= now:
                raise MarketError("The closing time has passed; move it later first.")
            if market.outcomes.filter(is_active=True).count() < 2:
                raise MarketError("A market needs at least 2 active outcomes.")
        MarketEvent.objects.create(
            market=market, from_status=market.status, to_status=to, actor=actor, reason=reason
        )
        market.status = to
        fields = ["status", "updated_at"]
        if actor is not None:
            market.updated_by = actor
            fields.append("updated_by")
        market.save(update_fields=fields)
    return market


def set_odds(outcome: Outcome, value, *, actor) -> Outcome:
    """Change an outcome's odds. Bets already placed keep the odds they were accepted at."""
    odds = clean_odds(value)
    with transaction.atomic():
        market = Market.objects.select_for_update().get(pk=outcome.market_id)
        if market.status not in EDITABLE_ODDS:
            raise MarketError(f"Odds can't change on a {market.status.lower()} market.")
        outcome = Outcome.objects.get(pk=outcome.pk)
        if outcome.odds != odds:
            OddsChange.objects.create(outcome=outcome, old=outcome.odds, new=odds, by=actor)
            outcome.odds = odds
            outcome.save(update_fields=["odds"])
    return outcome


def set_active(outcome: Outcome, active: bool, *, actor) -> Outcome:
    """Switch an outcome on or off for new bets (e.g. a team that won't play)."""
    with transaction.atomic():
        market = Market.objects.select_for_update().get(pk=outcome.market_id)
        if market.status not in EDITABLE_ODDS:
            raise MarketError(f"Choices can't change on a {market.status.lower()} market.")
        Outcome.objects.filter(pk=outcome.pk).update(is_active=active)
        if market.status == S.OPEN and market.outcomes.filter(is_active=True).count() < 2:
            raise MarketError("An open market needs at least 2 active choices; suspend it first.")
        MarketEvent.objects.create(
            market=market,
            from_status=market.status,
            to_status=market.status,
            actor=actor,
            reason=f"{outcome.label} {'switched on' if active else 'switched off'}",
        )
    return Outcome.objects.get(pk=outcome.pk)


def close_due_markets(now=None) -> int:
    """Flip OPEN/SUSPENDED markets past their closing time to CLOSED (for lists; bets are
    refused at closing time either way)."""
    now = now or timezone.now()
    n = 0
    for market in Market.objects.filter(status__in=[S.OPEN, S.SUSPENDED], closes_at__lte=now):
        try:
            transition(market, S.CLOSED, actor=None, reason="Closing time reached")
            n += 1
        except MarketError:
            pass
    return n


def accepting_bets(market: Market, now=None) -> bool:
    now = now or timezone.now()
    return market.status == S.OPEN and market.opens_at <= now < market.closes_at


# -- who may bet ---------------------------------------------------------------------------------


def own_team_ids(user) -> set[int]:
    """Teams a user plays for or belongs to: they can't bet on markets about them."""
    ids = set(user.memberships.filter(is_active=True).values_list("team_id", flat=True))
    player = getattr(user, "player", None)
    if player is not None and player.current_team_id:
        ids.add(player.current_team_id)
    return ids


# -- placing a bet -------------------------------------------------------------------------------


def clean_stake(stake) -> int:
    lo, hi = settings.PREDICTIONS_MIN_STAKE, settings.PREDICTIONS_MAX_STAKE
    if not isinstance(stake, int) or isinstance(stake, bool):
        raise MarketError("The stake must be a whole number of coins.", "stake")
    if not lo <= stake <= hi:
        raise MarketError(f"The stake must be between {lo} and {hi} coins.", "stake")
    return stake


def place_bet(
    user, *, market_id: int, outcome_id: int, stake, client_key: uuid.UUID, expected_odds=None
) -> tuple[Bet, bool]:
    """Take the stake and record the bet together, or do neither.

    The odds come from the outcome as it is when the market row is locked; anything the
    client says about odds is only compared, never used. Returns ``(bet, created)``: a
    repeat of the same ``client_key`` returns the first bet without charging again.
    """
    if not can_play(user):
        raise MarketError("League staff can't play predictions.", "not_allowed")
    stake = clean_stake(stake)

    def same(bet: Bet) -> tuple[Bet, bool]:
        if (bet.market_id, bet.outcome_id, bet.stake) != (market_id, outcome_id, stake):
            raise MarketError("This confirmation was already used for another bet.", "key_reused")
        return bet, False

    if existing := Bet.objects.filter(user=user, client_key=client_key).first():
        return same(existing)

    wallet = wallet_for(user)
    try:
        with transaction.atomic():
            market = Market.objects.select_for_update().filter(pk=market_id).first()
            if market is None or market.status == S.DRAFT:
                raise MarketError("This market doesn't exist.", "not_found")
            outcome = Outcome.objects.filter(pk=outcome_id, market=market).first()
            if outcome is None:
                raise MarketError("That choice isn't part of this market.", "outcome")
            if not accepting_bets(market):
                raise MarketError("This market isn't taking predictions now.", "closed")
            if not outcome.is_active:
                raise MarketError("That choice is no longer available.", "outcome")
            if market_team_ids(market) & own_team_ids(user):
                raise MarketError(
                    "You can't predict on a market about your own team.", "not_allowed"
                )
            if expected_odds is not None and clean_odds(expected_odds) != outcome.odds:
                raise MarketError(
                    f"The odds changed to {outcome.odds}. Check and confirm again.",
                    "odds_changed",
                    odds=str(outcome.odds),
                )
            bet = Bet.objects.create(
                user=user,
                market=market,
                outcome=outcome,
                stake=stake,
                odds_accepted=outcome.odds,
                potential_return=potential_return(stake, outcome.odds),
                client_key=client_key,
            )
            post_entry(wallet, Kind.STAKE, -stake, f"stake:{bet.pk}", bet=bet)
    except CoinError as exc:
        raise MarketError(str(exc), "coins") from exc
    except IntegrityError:
        # The same confirmation arrived twice at once and the other one won.
        existing = Bet.objects.filter(user=user, client_key=client_key).first()
        if existing is None:
            raise
        return same(existing)
    return bet, True
