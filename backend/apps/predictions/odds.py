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
from django.db.models import Count, F, Sum

from apps.league.models import Match, Player, Season, Team
from apps.results.models import MatchEvent, PlayerMatchResult, StandingRow, TeamMatchResult

from .markets import (
    BANDS,
    H2H,
    HANDICAPS,
    PLAYER_MARKETS,
    SEASON_MARKETS,
    SESSION_MARKETS,
    MarketError,
    check_fixture,
    clean_params,
)
from .models import MIN_ODDS, Market

C = Market.Category
HISTORY = 40  # a team's most recent published matches that count
PRIOR = 5  # matches' worth of league-wide results blended into every team
SIMS = 4000
SEASON_SIMS = 1000
FRAGGER_SIMS = 2000
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
    listed = params.get("teams") or ([params["team"]] if params.get("team") else [])
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
        elif category == C.TOTAL_KILLS:
            wins["yes"] += sum(k for _, k in result.values()) >= params["line"]
        elif category in HANDICAPS:
            a, b = (result[t] for t in listed)
            if category == C.KILLS_HANDICAP:
                lead = a[1] - b[1]
            else:
                points = [rule.placement_score(p) + rule.kill_score(k) for p, k in (a, b)]
                lead = points[0] - points[1]
            wins[f"team:{listed[0] if lead >= params['line'] else listed[1]}"] += 1
        elif category == C.FINISH_BAND:
            place = result[params["team"]][0]
            wins[next(c for c, (lo, hi) in BANDS.items() if lo <= place <= hi)] += 1
        elif category == C.FIRST_OUT:
            wins.update(f"team:{t}" for t in listed if result[t][0] == len(teams))
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
    if category in (C.BOOYAH, C.FIRST_OUT, *HANDICAPS):
        return {f"team:{t}": wins[f"team:{t}"] / SIMS for t in listed}
    if category == C.FINISH_BAND:
        return {c: wins[c] / SIMS for c in BANDS}
    return {"yes": wins["yes"] / SIMS, "no": 1 - wins["yes"] / SIMS}


# -- players --------------------------------------------------------------------------------------


@dataclass
class PlayerHistory:
    own: dict[int, list[tuple[int, int | None]]] = field(default_factory=dict)  # (kills, damage)
    pool: list[tuple[int, int | None]] = field(default_factory=list)
    per_match: int = DEFAULT_LOBBY * 4


def load_player_history() -> PlayerHistory:
    """Every player's most recent published (kills, damage dealt), newest first."""
    published = PlayerMatchResult.objects.filter(match__status=Match.Status.PUBLISHED)
    rows = published.order_by(
        F("match__started_at").desc(nulls_last=True), "-match_id"
    ).values_list("player_id", "kills", "damage_dealt")
    history = PlayerHistory()
    for player, kills, damage in rows:
        history.pool.append((kills, damage))
        own = history.own.setdefault(player, [])
        if len(own) < HISTORY:
            own.append((kills, damage))
    sizes = list(published.values("match").annotate(n=Count("id")).values_list("n", flat=True))
    if sizes:
        history.per_match = round(median(sizes))
    return history


def _blended(own: list, pool: list, hit) -> float:
    """The share of a player's (or team's) matches where ``hit`` is true, pulled towards the
    league-wide share when they have played little."""
    league = sum(map(hit, pool)) / len(pool) if pool else 0.0
    return (sum(map(hit, own)) + PRIOR * league) / (len(own) + PRIOR)


def _first_rates(firsts: Counter, played: Counter, ids: list[int], field_size: int) -> list[float]:
    """Chance each of ``ids`` is first (first blood, first to die): how often they have been,
    pulled towards an even share of the field when they have played little."""
    return [(firsts[i] + PRIOR / field_size) / (played[i] + PRIOR) for i in ids]


def _player_chances(category, params, rng: random.Random) -> dict[str, float]:
    history = load_player_history()
    if not history.pool:
        raise MarketError("There are no published player results to work from yet.", "no_history")
    if category in (C.PLAYER_KILLS, C.PLAYER_DAMAGE):
        index, line = (0 if category == C.PLAYER_KILLS else 1), params["line"]
        own = [r for r in history.own.get(params["player"], []) if r[index] is not None]
        pool = [r for r in history.pool if r[index] is not None]
        if not pool:
            raise MarketError("There are no damage figures to work from yet.", "no_history")
        yes = _blended(own, pool, lambda r: r[index] >= line)
        return {"yes": yes, "no": 1 - yes}
    players = params["players"]
    if category == C.FIRST_DEATH:
        published = MatchEvent.objects.filter(match__status=Match.Status.PUBLISHED)
        deaths = published.filter(
            kind=MatchEvent.Kind.DEATH, game_time_s__isnull=False, actor_player__isnull=False
        ).order_by("match_id", "game_time_s")
        firsts: Counter = Counter()
        seen: set[int] = set()
        for match, player in deaths.values_list("match_id", "actor_player_id"):
            if match not in seen:
                seen.add(match)
                firsts[player] += 1
        played = Counter(
            PlayerMatchResult.objects.filter(match_id__in=seen, player_id__in=players).values_list(
                "player_id", flat=True
            )
        )
        rates = _first_rates(firsts, played, players, history.per_match)
        return {f"player:{p}": r for p, r in zip(players, rates, strict=True)}

    def draw(player: int) -> int:
        own = history.own.get(player, [])
        if not own or rng.random() < PRIOR / (len(own) + PRIOR):
            return rng.choice(history.pool)[0]
        return rng.choice(own)[0]

    shares: defaultdict = defaultdict(float)
    ties = 0
    others = max(history.per_match - len(players), 0)
    for _ in range(SIMS):
        kills = {p: draw(p) for p in players}
        if category == C.PLAYER_H2H:
            a, b = players
            if kills[a] == kills[b]:
                ties += 1  # a tie refunds every bet
            else:
                shares[a if kills[a] > kills[b] else b] += 1
            continue
        field_best = max((rng.choice(history.pool)[0] for _ in range(others)), default=0)
        best = max(max(kills.values()), field_best)
        if best == 0:
            ties += 1  # nobody scores: the market is refunded
            continue
        leaders = [p for p, k in kills.items() if k == best]
        tied = len(leaders) + (field_best == best)  # the field counts as one more at most
        for p in leaders:
            shares[p] += 1 / tied
    decided = SIMS - ties
    if not decided:
        return {f"player:{p}": 1 / len(players) for p in players}
    return {f"player:{p}": shares[p] / decided for p in players}


def _first_blood_chances(params) -> dict[str, float]:
    teams = params["teams"]
    kills = (
        MatchEvent.objects.filter(
            match__status=Match.Status.PUBLISHED,
            kind=MatchEvent.Kind.KILL,
            game_time_s__isnull=False,
            actor_team__isnull=False,
        )
        .exclude(actor_team=F("target_team"))
        .order_by("match_id", "game_time_s")
    )
    firsts: Counter = Counter()
    seen: set[int] = set()
    for match, team in kills.values_list("match_id", "actor_team_id"):
        if match not in seen:
            seen.add(match)
            firsts[team] += 1
    if not seen:
        raise MarketError("There are no timed kills to work from yet.", "no_history")
    played = Counter(
        TeamMatchResult.objects.filter(match_id__in=seen, team_id__in=teams).values_list(
            "team_id", flat=True
        )
    )
    lobby = round(median(Counter(TeamMatchResult.objects.filter(match_id__in=seen).values_list(
        "match_id", flat=True)).values()))  # fmt: skip
    rates = _first_rates(firsts, played, teams, lobby)
    return {f"team:{t}": r for t, r in zip(teams, rates, strict=True)}


def _share_wins(shares: defaultdict, leaders: list[int], listed: list[int]) -> None:
    """Teams level at the top share the win (a dead heat pays odds / number tied)."""
    for t in leaders:
        if t in listed:
            shares[t] += 1 / len(leaders)


def _session_chances(category, params, sim, lobby, matches, season) -> dict[str, float]:
    """Session markets, and date-range team markets played as ``matches`` matches in a row."""
    listed = params.get("teams") or [params["team"]]
    teams = listed + [-n for n in range(1, max(lobby - len(listed), 0) + 1)]
    rule, tiebreakers = season.scoring_rule, season.tiebreakers
    shares: defaultdict = defaultdict(float)
    ties = 0
    for _ in range(SIMS):
        tallies = {t: Tally() for t in teams}
        for _ in range(matches):
            for t, (place, kills) in sim.match(teams).items():
                tallies[t].add(place, kills, rule)
        if category == C.SESSION_KILLS:
            shares["yes"] += tallies[params["team"]].kills >= params["line"]
            continue
        if category == C.SESSION_H2H:
            a, b = (tallies[t].total_points for t in listed)
            if a == b:
                ties += 1  # a tie refunds every bet
            else:
                shares[listed[0] if a > b else listed[1]] += 1
            continue
        if category == C.RANGE_TOP_N:
            keys = {t: _key(x, tiebreakers) for t, x in tallies.items()}
            team = params["team"]
            shares["yes"] += 1 + sum(k > keys[team] for k in keys.values()) <= params["n"]
            continue
        if category in (C.SESSION_WINNER, C.RANGE_WINNER):
            best = max(_key(x, tiebreakers) for x in tallies.values())
            leaders = [t for t, x in tallies.items() if _key(x, tiebreakers) == best]
        else:
            most = max(x.booyahs for x in tallies.values())
            leaders = [t for t, x in tallies.items() if x.booyahs == most]
        _share_wins(shares, leaders, listed)
    if category in (C.SESSION_KILLS, C.RANGE_TOP_N):
        return {"yes": shares["yes"] / SIMS, "no": 1 - shares["yes"] / SIMS}
    decided = SIMS - ties
    if not decided:
        return {f"team:{t}": 1 / len(listed) for t in listed}
    return {f"team:{t}": shares[t] / decided for t in listed}


def _fragger_chances(players, matches: int, sims: int, rng, start=None, field=None) -> dict:
    """Most kills over ``matches`` matches: ``start`` kills already scored (the season so far)
    and ``field``, the other players who could win (unnamed stand-ins when not given)."""
    history = load_player_history()
    if not history.pool:
        raise MarketError("There are no published player results to work from yet.", "no_history")
    start = start or {}
    if field is None:
        field = [-n for n in range(1, max(history.per_match - len(players), 0) + 1)]
    everyone = list(players) + [p for p in field if p not in players]

    def draw(player: int) -> int:
        own = history.own.get(player, [])
        if not own or rng.random() < PRIOR / (len(own) + PRIOR):
            return rng.choice(history.pool)[0]
        return rng.choice(own)[0]

    shares: defaultdict = defaultdict(float)
    nobody = 0
    for _ in range(sims):
        kills = {p: start.get(p, 0) + sum(draw(p) for _ in range(matches)) for p in everyone}
        best = max(kills.values())
        if best == 0:
            nobody += 1  # nobody scores: the market is refunded
            continue
        leaders = [p for p, k in kills.items() if k == best]
        for p in leaders:
            if p in players:
                shares[p] += 1 / len(leaders)
    decided = sims - nobody
    if not decided:
        return {f"player:{p}": 1 / len(players) for p in players}
    return {f"player:{p}": shares[p] / decided for p in players}


def _season_fragger_chances(params, matches_left, season, rng) -> dict:
    so_far = dict(
        PlayerMatchResult.objects.filter(
            match__match_day__stage__season=season, match__status=Match.Status.PUBLISHED
        )
        .values("player")
        .annotate(k=Sum("kills"))
        .values_list("player", "k")
    )
    return _fragger_chances(
        params["players"], matches_left, SEASON_SIMS, rng, start=so_far, field=list(so_far)
    )


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
    left = DEFAULT_MATCHES_LEFT if matches_left is None else matches_left
    if category == C.SEASON_FRAGGER:
        chances = _season_fragger_chances(params, left, season, rng)
        info.update(matches_left=left, simulations=SEASON_SIMS)
    elif category == C.RANGE_FRAGGER:
        chances = _fragger_chances(params["players"], left, FRAGGER_SIMS, rng)
        info.update(matches_left=left, simulations=FRAGGER_SIMS)
    elif category in (C.RANGE_WINNER, C.RANGE_TOP_N):
        chances = _session_chances(category, params, sim, lobby, left, season)
        info.update(matches_left=left, simulations=SIMS)
    elif category in SEASON_MARKETS:
        chances = _season_chances(category, params, sim, lobby, left, season)
        info.update(matches_left=left, simulations=SEASON_SIMS)
    elif category == C.SESSION_FRAGGER:
        matches = session_length(season, fixture)
        chances = _fragger_chances(params["players"], matches, FRAGGER_SIMS, rng)
        info.update(matches=matches, simulations=FRAGGER_SIMS)
    elif category in SESSION_MARKETS:
        matches = session_length(season, fixture)
        chances = _session_chances(category, params, sim, lobby, matches, season)
        info.update(matches=matches, simulations=SIMS)
    elif category in PLAYER_MARKETS:
        chances = _player_chances(category, params, rng)
        info.update(matches=1, simulations=SIMS)
    elif category == C.FIRST_BLOOD:
        chances = _first_blood_chances(params)
        info.update(matches=1)
    else:
        chances = _match_chances(category, params, sim, lobby, season.scoring_rule)
        info.update(matches=1, simulations=SIMS)

    margin = settings.PREDICTIONS_ODDS_MARGIN
    listed = params.get("teams") or ([params["team"]] if params.get("team") else [])
    names = dict(Team.objects.filter(pk__in=listed).values_list("pk", "name"))
    teams = [{"id": t, "name": names[t], "matches": len(history.own.get(t, []))} for t in listed]
    thin = [t["name"] for t in teams if t["matches"] < PRIOR]
    people = params.get("players") or ([params["player"]] if params.get("player") else [])
    if people:
        counts = Counter(
            PlayerMatchResult.objects.filter(
                player_id__in=people, match__status=Match.Status.PUBLISHED
            ).values_list("player_id", flat=True)
        )
        names = dict(Player.objects.filter(pk__in=people).values_list("pk", "display_name"))
        info["players"] = [
            {"id": p, "name": names[p], "matches": min(counts[p], HISTORY)} for p in people
        ]
        thin += [p["name"] for p in info["players"] if p["matches"] < PRIOR]
    notes = []
    if thin:
        names = thin[0] if len(thin) == 1 else f"{', '.join(thin[:-1])} and {thin[-1]}"
        notes.append(
            f"{names} {'has' if len(thin) == 1 else 'have'} fewer than {PRIOR} published "
            "matches, so the odds lean on league averages."
        )
    if category in (
        C.BOOYAH,
        C.SESSION_WINNER,
        C.MOST_BOOYAHS,
        C.OVERALL_WINNER,
        C.FIRST_OUT,
        C.FIRST_BLOOD,
        C.TOP_FRAGGER,
        C.FIRST_DEATH,
        C.RANGE_WINNER,
        C.SESSION_FRAGGER,
        C.RANGE_FRAGGER,
        C.SEASON_FRAGGER,
    ):
        if sum(chances.values()) < 0.99:
            notes.append("Choices that aren't listed can win too, so the chances add up to less.")
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
