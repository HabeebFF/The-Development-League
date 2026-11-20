"""Suggested odds: each outcome's chance from past results, priced with a small margin.

Staff still set the odds; this only pre-fills the new market form. Chances come from playing
the market's match, session or rest of the season many times over. In each simulated match
every team repeats one of its own recent published results, picked at random, and teams are
placed in the order those results finished. A team with little history leans on the whole
league's results instead. Odds are 1 / (chance x (1 + margin)), rounded down to a tidy step.

When the map is known (drawn when scrim sign-up opens, ``apps.scrims.maps``), a team or
player repeats a result from that map more often: the more they have played it, the more
(``MAP_PRIOR`` matches' worth of their overall record is mixed in, so 1 or 2 games on a map
don't swing the odds). Stand-ins and players with no history use the league's results on that
map once there are enough of them. Session markets play each match on its own drawn map.
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
from apps.maps.models import Map
from apps.results.models import MatchEvent, PlayerMatchResult, StandingRow, TeamMatchResult
from apps.scrims.models import ScrimSession

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
MAP_PRIOR = 8  # matches' worth of a team's overall record mixed into its record on a map
MAP_POOL_MIN = 30  # league results on a map needed before stand-ins use them
DEFAULT_LOBBY = 12
DEFAULT_SESSION = 6
DEFAULT_MATCHES_LEFT = 10
MAX_MATCHES_LEFT = 60
MAX_SUGGESTED = Decimal("25")  # long shots stop here; staff can type more by hand
# Markets where exactly one listed choice (or someone not listed) wins.
ONE_WINNER = (
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
)
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
    on_map: dict[tuple[int, int], list[Draw]] = field(default_factory=dict)  # (team, map)
    map_pool: dict[int, list[Draw]] = field(default_factory=dict)

    def league(self, map_id: int | None) -> list[Draw]:
        """The league's results to lean on: on this map, once there are enough."""
        on = self.map_pool.get(map_id) if map_id else None
        return on if on and len(on) >= MAP_POOL_MIN else self.pool


def load_history() -> History:
    """Every team's most recent published results, all seasons, newest first."""
    published = TeamMatchResult.objects.filter(match__status=Match.Status.PUBLISHED)
    lobby = dict(published.values("match").annotate(n=Count("id")).values_list("match", "n"))
    rows = published.order_by(
        F("match__started_at").desc(nulls_last=True), "-match_id"
    ).values_list("team_id", "match_id", "placement", "kills", "match__map_id")
    history = History()
    for team, match, placement, kills, map_id in rows:
        size = max(lobby[match], placement)
        draw = Draw((placement - 0.5) / size, kills)
        history.pool.append(draw)
        own = history.own.setdefault(team, [])
        if len(own) < HISTORY:
            own.append(draw)
        if map_id:
            history.map_pool.setdefault(map_id, []).append(draw)
            on = history.on_map.setdefault((team, map_id), [])
            if len(on) < HISTORY:
                on.append(draw)
    return history


def _pick(rng, own: list, on_map: list, league: list):
    """One past result: from the player's or team's record on the map (weighted by how much
    they've played it), else their overall record, else (little history) the league's."""
    if on_map and rng.random() < len(on_map) / (len(on_map) + MAP_PRIOR):
        return rng.choice(on_map)
    if not own or rng.random() < PRIOR / (len(own) + PRIOR):
        return rng.choice(league)
    return rng.choice(own)


class Simulator:
    def __init__(self, history: History, rng: random.Random):
        self.history, self.rng = history, rng

    def draw(self, team: int, map_id: int | None = None) -> Draw:
        h = self.history
        on_map = h.on_map.get((team, map_id), []) if map_id else []
        return _pick(self.rng, h.own.get(team, []), on_map, h.league(map_id))

    def match(self, teams: list[int], map_id: int | None = None) -> dict[int, tuple[int, int]]:
        """One simulated match: ``{team: (placement, kills)}``."""
        draws = {t: self.draw(t, map_id) for t in teams}
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


def _match_chances(category, params, sim, lobby, rule, map_id=None) -> dict[str, float]:
    listed = params.get("teams") or ([params["team"]] if params.get("team") else [])
    teams = listed + [-n for n in range(1, max(lobby - len(listed), 0) + 1)]  # stand-ins
    wins: Counter = Counter()
    ties = 0
    for _ in range(SIMS):
        result = sim.match(teams, map_id)
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


# What each player result holds, by position: (kills, damage dealt, knocks, deaths). Damage,
# knocks and deaths are None on matches whose logs didn't have them.
STAT = {"kills": 0, "damage": 1, "knocks": 2, "deaths": 3}
LINE_STAT = {
    C.PLAYER_KILLS: "kills",
    C.PLAYER_DAMAGE: "damage",
    C.PLAYER_KNOCKS: "knocks",
    C.SESSION_DEATHS: "deaths",
}


@dataclass
class PlayerHistory:
    own: dict[int, list[tuple]] = field(default_factory=dict)
    pool: list[tuple] = field(default_factory=list)
    on_map: dict[tuple[int, int], list[tuple]] = field(default_factory=dict)  # (player, map)
    map_pool: dict[int, list[tuple]] = field(default_factory=dict)
    per_match: int = DEFAULT_LOBBY * 4

    def records(self, player: int, map_id: int | None, stat: str = "kills"):
        """(own, on this map, league) results that have ``stat``."""
        i = STAT[stat]

        def has(rows):
            return [r for r in rows if r[i] is not None]

        own = has(self.own.get(player, []))
        on_map = has(self.on_map.get((player, map_id), [])) if map_id else []
        league = has(self.map_pool.get(map_id, [])) if map_id else []
        if len(league) < MAP_POOL_MIN:
            league = has(self.pool)
        return own, on_map, league


def load_player_history() -> PlayerHistory:
    """Every player's most recent published (kills, damage, knocks, deaths), newest first."""
    published = PlayerMatchResult.objects.filter(match__status=Match.Status.PUBLISHED)
    rows = published.order_by(
        F("match__started_at").desc(nulls_last=True), "-match_id"
    ).values_list("player_id", "kills", "damage_dealt", "knocks", "deaths", "match__map_id")
    history = PlayerHistory()
    for player, kills, damage, knocks, deaths, map_id in rows:
        row = (kills, damage, knocks, deaths)
        history.pool.append(row)
        own = history.own.setdefault(player, [])
        if len(own) < HISTORY:
            own.append(row)
        if map_id:
            history.map_pool.setdefault(map_id, []).append(row)
            on = history.on_map.setdefault((player, map_id), [])
            if len(on) < HISTORY:
                on.append(row)
    sizes = list(published.values("match").annotate(n=Count("id")).values_list("n", flat=True))
    if sizes:
        history.per_match = round(median(sizes))
    return history


def _blended(own: list, pool: list, hit, on_map: list | None = None) -> float:
    """The share of a player's (or team's) matches where ``hit`` is true, pulled towards the
    league-wide share when they have played little, and towards their share on the map when
    they have played it."""
    league = sum(map(hit, pool)) / len(pool) if pool else 0.0
    overall = (sum(map(hit, own)) + PRIOR * league) / (len(own) + PRIOR)
    if not on_map:
        return overall
    return (sum(map(hit, on_map)) + MAP_PRIOR * overall) / (len(on_map) + MAP_PRIOR)


def _first_rates(firsts: Counter, played: Counter, ids: list[int], field_size: int) -> list[float]:
    """Chance each of ``ids`` is first (first blood, first to die): how often they have been,
    pulled towards an even share of the field when they have played little."""
    return [(firsts[i] + PRIOR / field_size) / (played[i] + PRIOR) for i in ids]


def _player_chances(category, params, rng: random.Random, map_id=None) -> dict[str, float]:
    history = load_player_history()
    if not history.pool:
        raise MarketError("There are no published player results to work from yet.", "no_history")
    if category in LINE_STAT:
        stat, line = LINE_STAT[category], params["line"]
        index = STAT[stat]
        own, on_map, pool = history.records(params["player"], map_id, stat)
        if not pool:
            raise MarketError(f"There are no {stat} figures to work from yet.", "no_history")
        yes = _blended(own, pool, lambda r: r[index] >= line, on_map)
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
        return _pick(rng, *history.records(player, map_id))[0]

    league = history.records(0, map_id)[2]
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
        field_best = max((rng.choice(league)[0] for _ in range(others)), default=0)
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


def _map_of(maps: list | None, n: int) -> int | None:
    return maps[n] if maps and n < len(maps) else None


def _session_chances(category, params, sim, lobby, matches, season, maps=None) -> dict[str, float]:
    """Session markets, and date-range team markets played as ``matches`` matches in a row
    (each on its drawn map, when ``maps`` are known)."""
    listed = params.get("teams") or [params["team"]]
    teams = listed + [-n for n in range(1, max(lobby - len(listed), 0) + 1)]
    rule, tiebreakers = season.scoring_rule, season.tiebreakers
    shares: defaultdict = defaultdict(float)
    ties = 0
    for _ in range(SIMS):
        tallies = {t: Tally() for t in teams}
        for n in range(matches):
            for t, (place, kills) in sim.match(teams, _map_of(maps, n)).items():
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


def _fragger_chances(
    players, matches: int, sims: int, rng, start=None, field=None, maps=None
) -> dict:
    """Most kills over ``matches`` matches: ``start`` kills already scored (the season so far)
    and ``field``, the other players who could win (unnamed stand-ins when not given). Each
    match is played on its drawn map when ``maps`` are known."""
    history = load_player_history()
    if not history.pool:
        raise MarketError("There are no published player results to work from yet.", "no_history")
    start = start or {}
    if field is None:
        field = [-n for n in range(1, max(history.per_match - len(players), 0) + 1)]
    everyone = list(players) + [p for p in field if p not in players]

    def draw(player: int, n: int) -> int:
        return _pick(rng, *history.records(player, _map_of(maps, n)))[0]

    shares: defaultdict = defaultdict(float)
    nobody = 0
    for _ in range(sims):
        kills = {p: start.get(p, 0) + sum(draw(p, n) for n in range(matches)) for p in everyone}
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


def _session_deaths_chances(params, matches: int, rng, maps=None) -> dict[str, float]:
    """A player's deaths over the session: each match repeats one of their past matches (on
    that match's map when it's known), added up."""
    history = load_player_history()
    i = STAT["deaths"]
    player, line = params["player"], params["line"]
    if not history.records(player, None, "deaths")[2]:
        raise MarketError("There are no death figures to work from yet.", "no_history")
    records = [history.records(player, _map_of(maps, n), "deaths") for n in range(matches)]
    yes = 0
    for _ in range(FRAGGER_SIMS):
        total = sum(_pick(rng, *r)[i] for r in records)
        yes += total >= line
    return {"yes": yes / FRAGGER_SIMS, "no": 1 - yes / FRAGGER_SIMS}


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


# -- maps -----------------------------------------------------------------------------------------


def session_maps(fixture) -> list[int]:
    """The maps of a whole-session fixture's matches, in order (empty when not drawn)."""
    if fixture is None or fixture.match_number is not None:
        return []
    scrim = ScrimSession.objects.filter(date=fixture.date, session=fixture.session).first()
    return list(scrim.maps) if scrim and scrim.maps else []


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
    map_id = fixture.map_id if fixture is not None and fixture.match_number else None
    maps = session_maps(fixture)
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
        matches = len(maps) or session_length(season, fixture)
        chances = _fragger_chances(params["players"], matches, FRAGGER_SIMS, rng, maps=maps)
        info.update(matches=matches, simulations=FRAGGER_SIMS)
    elif category == C.SESSION_DEATHS:
        matches = len(maps) or session_length(season, fixture)
        chances = _session_deaths_chances(params, matches, rng, maps)
        info.update(matches=matches, simulations=FRAGGER_SIMS)
    elif category in SESSION_MARKETS:
        matches = len(maps) or session_length(season, fixture)
        chances = _session_chances(category, params, sim, lobby, matches, season, maps)
        info.update(matches=matches, simulations=SIMS)
    elif category in PLAYER_MARKETS:
        chances = _player_chances(category, params, rng, map_id)
        info.update(matches=1, simulations=SIMS)
    elif category == C.FIRST_BLOOD:
        chances = _first_blood_chances(params)
        info.update(matches=1)
    else:
        chances = _match_chances(category, params, sim, lobby, season.scoring_rule, map_id)
        info.update(matches=1, simulations=SIMS)
    named = dict(Map.objects.filter(pk__in=[map_id, *maps]).values_list("pk", "name"))
    info["map"] = named.get(map_id)
    info["maps"] = [named.get(m) for m in maps]

    margin = settings.PREDICTIONS_ODDS_MARGIN
    if category in ONE_WINNER and sum(chances.values()) > 1:
        # Only one choice can win, so the chances can't add up to more than all of it.
        total = sum(chances.values())
        chances = {code: c / total for code, c in chances.items()}
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
    if category in ONE_WINNER:
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
