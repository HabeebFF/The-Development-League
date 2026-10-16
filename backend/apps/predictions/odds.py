"""Suggested odds: each outcome's chance from past results, priced with a small margin.

Staff still set the odds; this only pre-fills the new market form. Chances come from playing
the market's match, session or rest of the season many times over. In each simulated match
every team repeats one of its own recent published results, picked at random, and teams are
placed in the order those results finished. A team with little history leans on the whole
league's results instead. Odds are 1 / (chance x (1 + margin)), rounded down to a tidy step.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, Decimal
from statistics import median

from django.conf import settings
from django.db.models import Count, F

from apps.league.models import Match, Season, Team
from apps.results.models import StandingRow, TeamMatchResult

from .markets import H2H, SEASON_MARKETS, SESSION_MARKETS, MarketError, check_fixture, clean_params
from .models import MIN_ODDS, Market

C = Market.Category
HISTORY = 40  # a team's most recent published matches that count
PRIOR = 5  # matches' worth of league-wide results blended into every team
SIMS = 4000
SEASON_SIMS = 1000
DEFAULT_LOBBY = 12
DEFAULT_SESSION = 6
DEFAULT_MATCHES_LEFT = 10
MAX_MATCHES_LEFT = 60
MAX_SUGGESTED = Decimal("500")
STEPS = [(2, "0.01"), (5, "0.05"), (10, "0.1"), (20, "0.5")]


@dataclass(frozen=True)
class Draw:
    spot: float  # where the team finished as a share of its lobby: near 0 is first
    kills: int


@dataclass
class Tally:
    total_points: int = 0
    booyahs: int = 0
    kills: int = 0
    placement_points: int = 0
    last_match: int = 0

    def add(self, place: int, kills: int, rule) -> None:
        placement = rule.placement_score(place)
        points = placement + rule.kill_score(kills)
        self.total_points += points
        self.booyahs += place == 1
        self.kills += kills
        self.placement_points += placement
        self.last_match = points


@dataclass
class History:
    own: dict[int, list[Draw]] = field(default_factory=dict)
    pool: list[Draw] = field(default_factory=list)


def load_history() -> History:
    """Every team's most recent published results, all seasons, newest first."""
    published = TeamMatchResult.objects.filter(match__status=Match.Status.PUBLISHED)
    lobby = dict(published.values("match").annotate(n=Count("id")).values_list("match", "n"))
    rows = published.order_by(
        F("match__started_at").desc(nulls_last=True), "-match_id"
    ).values_list("team_id", "match_id", "placement", "kills")
    history = History()
    for team, match, placement, kills in rows:
        size = max(lobby[match], placement)
        draw = Draw((placement - 0.5) / size, kills)
        history.pool.append(draw)
        own = history.own.setdefault(team, [])
        if len(own) < HISTORY:
            own.append(draw)
    return history


class Simulator:
    def __init__(self, history: History, rng: random.Random):
        self.history, self.rng = history, rng

    def draw(self, team: int) -> Draw:
        own = self.history.own.get(team, [])
        if not own or self.rng.random() < PRIOR / (len(own) + PRIOR):
            return self.rng.choice(self.history.pool)
        return self.rng.choice(own)

    def match(self, teams: list[int]) -> dict[int, tuple[int, int]]:
        """One simulated match: ``{team: (placement, kills)}``."""
        draws = {t: self.draw(t) for t in teams}
        order = sorted(teams, key=lambda t: (draws[t].spot, self.rng.random()))
        return {t: (n, draws[t].kills) for n, t in enumerate(order, start=1)}


# -- sizes ----------------------------------------------------------------------------------------


def lobby_size(season: Season) -> int:
    """Teams in a typical match this season (or in any season, before this one has matches)."""
    for scope in ({"match__match_day__stage__season": season}, {}):
        sizes = list(
            TeamMatchResult.objects.filter(match__status=Match.Status.PUBLISHED, **scope)
            .values("match")
            .annotate(n=Count("id"))
            .values_list("n", flat=True)
        )
        if sizes:
            return round(median(sizes))
    return DEFAULT_LOBBY


def session_length(season: Season, fixture) -> int:
    """Matches in the session: the linked match day's, or a typical day's this season."""
    if fixture is not None and fixture.match_day_id:
        played = fixture.match_day.matches.exclude(status=Match.Status.DRAFT).count()
        if played:
            return played
    counts = list(
        Match.objects.filter(match_day__stage__season=season, status=Match.Status.PUBLISHED)
        .values("match_day")
        .annotate(n=Count("id"))
        .values_list("n", flat=True)
    )
    return round(median(counts)) if counts else DEFAULT_SESSION


# -- chances --------------------------------------------------------------------------------------


def _key(tally: Tally, tiebreakers: list[str]) -> tuple:
    return tuple(getattr(tally, tb) for tb in tiebreakers if hasattr(tally, tb))


def _match_chances(category, params, sim, lobby, rule) -> dict[str, float]:
    listed = params.get("teams") or [params["team"]]
    teams = listed + [-n for n in range(1, max(lobby - len(listed), 0) + 1)]  # stand-ins
    wins: Counter = Counter()
    ties = 0
    for _ in range(SIMS):
        result = sim.match(teams)
        if category == C.BOOYAH:
            wins.update(f"team:{t}" for t in listed if result[t][0] == 1)
        elif category == C.TOP_N:
            wins["yes"] += result[params["team"]][0] <= params["n"]
        elif category == C.TEAM_KILLS:
            wins["yes"] += result[params["team"]][1] >= params["line"]
        else:
            a, b = (result[t] for t in listed)
            if category == C.H2H_PLACEMENT:
                score = (-a[0], -b[0])
            elif category == C.H2H_KILLS:
                score = (a[1], b[1])
            else:
                score = tuple(rule.placement_score(p) + rule.kill_score(k) for p, k in (a, b))
            if score[0] == score[1]:
                ties += 1  # a tie refunds every bet, so it doesn't count either way
            else:
                wins[f"team:{listed[0] if score[0] > score[1] else listed[1]}"] += 1
    if category in H2H:
        decided = SIMS - ties
        if not decided:
            return {f"team:{t}": 0.5 for t in listed}
        return {f"team:{t}": wins[f"team:{t}"] / decided for t in listed}
    if category == C.BOOYAH:
        return {f"team:{t}": wins[f"team:{t}"] / SIMS for t in listed}
    return {"yes": wins["yes"] / SIMS, "no": 1 - wins["yes"] / SIMS}


def _share_wins(shares: defaultdict, leaders: list[int], listed: list[int]) -> None:
    """Teams level at the top share the win (a dead heat pays odds / number tied)."""
    for t in leaders:
        if t in listed:
            shares[t] += 1 / len(leaders)


def _session_chances(category, params, sim, lobby, matches, season) -> dict[str, float]:
    listed = params["teams"]
    teams = listed + [-n for n in range(1, max(lobby - len(listed), 0) + 1)]
    rule, tiebreakers = season.scoring_rule, season.tiebreakers
    shares: defaultdict = defaultdict(float)
    for _ in range(SIMS):
        tallies = {t: Tally() for t in teams}
        for _ in range(matches):
            for t, (place, kills) in sim.match(teams).items():
                tallies[t].add(place, kills, rule)
        if category == C.SESSION_WINNER:
            best = max(_key(x, tiebreakers) for x in tallies.values())
            leaders = [t for t, x in tallies.items() if _key(x, tiebreakers) == best]
        else:
            most = max(x.booyahs for x in tallies.values())
            leaders = [t for t, x in tallies.items() if x.booyahs == most]
        _share_wins(shares, leaders, listed)
    return {f"team:{t}": shares[t] / SIMS for t in listed}


def _season_chances(category, params, sim, lobby, matches_left, season) -> dict[str, float]:
    rule, tiebreakers = season.scoring_rule, season.tiebreakers
    start = {
        r.team_id: Tally(
            r.total_points, r.booyahs, r.kills, r.placement_points, r.last_match_points or 0
        )
        for r in StandingRow.objects.filter(season=season, scope="season")
    }
    listed = params.get("teams") or [params["team"]]
    for t in listed:
        start.setdefault(t, Tally())
    teams = list(start)
    lobbies = max(1, -(-len(teams) // lobby))  # rounded up
    shares: defaultdict = defaultdict(float)
    for _ in range(SEASON_SIMS):
        tallies = {t: Tally(**vars(x)) for t, x in start.items()}
        for _ in range(matches_left):
            sim.rng.shuffle(teams)
            for n in range(lobbies):
                for t, (place, kills) in sim.match(teams[n::lobbies]).items():
                    tallies[t].add(place, kills, rule)
        keys = {t: _key(x, tiebreakers) for t, x in tallies.items()}
        if category == C.OVERALL_WINNER:
            best = max(keys.values())
            _share_wins(shares, [t for t, k in keys.items() if k == best], listed)
        else:
            team = params["team"]
            rank = 1 + sum(k > keys[team] for k in keys.values())  # shared ranks: 1, 2, 2, 4
            shares[team] += rank <= params["n"]
    if category == C.OVERALL_WINNER:
        return {f"team:{t}": shares[t] / SEASON_SIMS for t in listed}
    yes = shares[params["team"]] / SEASON_SIMS
    return {"yes": yes, "no": 1 - yes}


# -- odds -----------------------------------------------------------------------------------------


def price(chance: float, margin: float) -> Decimal:
    """Odds for a chance, keeping ``margin`` back, rounded down to a tidy step."""
    if chance <= 0:
        return MAX_SUGGESTED.quantize(Decimal("0.01"))
    raw = Decimal(str(1 / (chance * (1 + margin))))
    step = next((Decimal(s) for top, s in STEPS if raw < top), Decimal(1))
    odds = (raw / step).to_integral_value(rounding=ROUND_FLOOR) * step
    return min(max(odds, MIN_ODDS), MAX_SUGGESTED).quantize(Decimal("0.01"))


def suggest_odds(
    *, season: Season, category: str, params: dict, fixture=None, matches_left=None
) -> dict:
    """Suggested odds for a market that hasn't been made yet; raises ``MarketError``."""
    params = clean_params(category, params)
    check_fixture(category, fixture)
    history = load_history()
    if not history.pool:
        raise MarketError("There are no published results to work from yet.", "no_history")
    rng = random.Random(f"{season.pk}:{category}:{sorted(params.items())}:{fixture and fixture.pk}")
    sim, lobby = Simulator(history, rng), lobby_size(season)
    info: dict = {"lobby": lobby}
    if category in SEASON_MARKETS:
        left = DEFAULT_MATCHES_LEFT if matches_left is None else matches_left
        chances = _season_chances(category, params, sim, lobby, left, season)
        info.update(matches_left=left, simulations=SEASON_SIMS)
    elif category in SESSION_MARKETS:
        matches = session_length(season, fixture)
        chances = _session_chances(category, params, sim, lobby, matches, season)
        info.update(matches=matches, simulations=SIMS)
    else:
        chances = _match_chances(category, params, sim, lobby, season.scoring_rule)
        info.update(matches=1, simulations=SIMS)

    margin = settings.PREDICTIONS_ODDS_MARGIN
    listed = params.get("teams") or [params["team"]]
    names = dict(Team.objects.filter(pk__in=listed).values_list("pk", "name"))
    teams = [{"id": t, "name": names[t], "matches": len(history.own.get(t, []))} for t in listed]
    thin = [t["name"] for t in teams if t["matches"] < PRIOR]
    notes = []
    if thin:
        names = thin[0] if len(thin) == 1 else f"{', '.join(thin[:-1])} and {thin[-1]}"
        notes.append(
            f"{names} {'has' if len(thin) == 1 else 'have'} fewer than {PRIOR} published "
            "matches, so the odds lean on league averages."
        )
    if category in (C.BOOYAH, C.SESSION_WINNER, C.MOST_BOOYAHS, C.OVERALL_WINNER):
        if sum(chances.values()) < 0.99:
            notes.append("Teams that aren't listed can win too, so the chances add up to less.")
    if any(c * (1 + margin) >= 1 / float(MIN_ODDS) for c in chances.values()):
        notes.append(
            f"An outcome is so likely its odds sit at the {MIN_ODDS} minimum, "
            "which pays out more than it should. Think about leaving it out."
        )
    return {
        "odds": {code: str(price(c, margin)) for code, c in chances.items()},
        "chances": {code: round(c, 4) for code, c in chances.items()},
        "margin": margin,
        "teams": teams,
        "notes": notes,
        **info,
    }
