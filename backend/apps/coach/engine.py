"""The coach's analysis engine: how a team plays, worked out from our match data only.

Everything here is plain arithmetic over what the logs recorded. The output is a list of
*facts*, each with the matches it rests on, so any sentence the coach writes later can be
traced back to real matches (and checked).

The measuring functions take plain dataclasses (``Game``) so they can be tested without a
database; ``load_games`` builds those from the database.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from apps.maps.calibration import point_in_polygon
from apps.rotations.paths import TeamPath

# A claim needs at least this many matches behind it.
MIN_MATCHES = 3
# Kills and knocks between the same two teams this close in time are one fight.
FIGHT_GAP_S = 30.0
# Another team landing this close means the drop was contested.
CONTEST_M = 200.0
# Unnamed spots: deaths and drops this close together count as the same place.
SPOT_M = 150.0
# Entering the next zone this long before it closes counts as rotating early.
EARLY_S = 45.0


# -- Inputs ---------------------------------------------------------------------------------


@dataclass
class Zone:
    number: int  # 1 = Zone 1
    x: float
    z: float
    r: float
    announced_s: float
    closes_s: float


@dataclass
class Hit:
    t: float
    kind: str  # "KNOCK" or "KILL"
    actor_team: int
    target_team: int
    target: int | None  # victim entity
    x: float | None = None  # victim position, when logged
    z: float | None = None


@dataclass
class Area:
    name: str
    polygon: list[list[float]]


@dataclass
class TeamGame:
    team: int
    placement: int
    eliminated_s: float | None
    path: TeamPath | None
    deaths: list[tuple[float, float, float]] = field(default_factory=list)  # final deaths t, x, z


@dataclass
class Game:
    match: int
    label: str
    map: str
    zones: list[Zone]
    hits: list[Hit]
    teams: dict[int, TeamGame]
    areas: list[Area] = field(default_factory=list)


# -- Per-match measures ---------------------------------------------------------------------


@dataclass
class ZoneEntry:
    zone: int
    lead_s: float | None  # seconds inside before it closed; negative = got in late; None = never
    edge: float | None  # distance from the centre / radius when it closed (>1 = outside)


@dataclass
class Fight:
    opponent: int
    t: float
    zone: int
    started: bool
    downs_for: int
    downs_against: int
    place: str | None

    @property
    def result(self) -> str:
        if self.downs_for > self.downs_against:
            return "won"
        return "lost" if self.downs_for < self.downs_against else "even"


@dataclass
class Spot:
    name: str | None  # a named area, or None for an unnamed spot
    x: float
    z: float


@dataclass
class TeamMatch:
    match: int
    label: str
    map: str
    placement: int
    drop: Spot | None
    contested_by: list[int]
    entries: list[ZoneEntry]
    fights: list[Fight]
    deaths: list[Spot]
    kills: int
    knocks: int


def area_at(areas: Sequence[Area], x: float, z: float) -> str | None:
    for a in areas:
        if point_in_polygon(x, z, a.polygon):
            return a.name
    return None


def zone_at(zones: Sequence[Zone], t: float) -> int:
    """The zone being played at t: 1 until Zone 1 closes, then 2, ..."""
    closed = sum(1 for z in zones if z.closes_s <= t)
    return min(closed + 1, max(len(zones), 1))


def _landing(path: TeamPath | None) -> tuple[float, float, float] | None:
    if path is None or not path.segments:
        return None
    at = path.at(path.landed_s) if path.landed_s is not None else None
    return at or path.segments[0][0]


def zone_entries(game: Game, team: TeamGame) -> list[ZoneEntry]:
    """When the team got inside each next safe zone, and where it stood when the zone closed."""
    out = []
    if team.path is None or not team.path.segments:
        return out
    end_t = team.path.end[0]
    for zone in game.zones:
        alive_at_close = team.eliminated_s is None or team.eliminated_s > zone.closes_s
        if not alive_at_close or end_t < zone.closes_s:
            break
        entered = None
        t = zone.announced_s
        while t <= zone.closes_s + 60:
            p = team.path.at(t)
            if p is not None and math.hypot(p[1] - zone.x, p[2] - zone.z) <= zone.r:
                entered = t
                break
            t += 1.0
        at_close = team.path.at(zone.closes_s)
        edge = (
            round(math.hypot(at_close[1] - zone.x, at_close[2] - zone.z) / zone.r, 2)
            if at_close is not None and zone.r > 0
            else None
        )
        lead = round(zone.closes_s - entered, 1) if entered is not None else None
        out.append(ZoneEntry(zone.number, lead, edge))
    return out


def fights(game: Game, team_id: int) -> list[Fight]:
    """Kills and knocks between this team and one other, grouped into fights."""
    by_opponent: dict[int, list[Hit]] = defaultdict(list)
    for h in sorted(game.hits, key=lambda h: h.t):
        if h.actor_team == h.target_team:
            continue
        if h.actor_team == team_id:
            by_opponent[h.target_team].append(h)
        elif h.target_team == team_id:
            by_opponent[h.actor_team].append(h)
    out = []
    for opponent, hits in by_opponent.items():
        groups: list[list[Hit]] = []
        for h in hits:
            if groups and h.t - groups[-1][-1].t <= FIGHT_GAP_S:
                groups[-1].append(h)
            else:
                groups.append([h])
        for g in groups:
            ours = {h.target for h in g if h.actor_team == team_id}
            theirs = {h.target for h in g if h.actor_team == opponent}
            where = next((h for h in g if h.x is not None), None)
            place = area_at(game.areas, where.x, where.z) if where else None
            out.append(
                Fight(
                    opponent=opponent,
                    t=g[0].t,
                    zone=zone_at(game.zones, g[0].t),
                    started=g[0].actor_team == team_id,
                    downs_for=len(ours),
                    downs_against=len(theirs),
                    place=place,
                )
            )
    return sorted(out, key=lambda f: f.t)


def measure(game: Game, team_id: int) -> TeamMatch:
    team = game.teams[team_id]
    landing = _landing(team.path)
    drop = None
    contested = []
    if landing is not None:
        drop = Spot(area_at(game.areas, landing[1], landing[2]), landing[1], landing[2])
        for other_id, other in game.teams.items():
            if other_id == team_id:
                continue
            theirs = _landing(other.path)
            if theirs and math.hypot(theirs[1] - landing[1], theirs[2] - landing[2]) <= CONTEST_M:
                contested.append(other_id)
    return TeamMatch(
        match=game.match,
        label=game.label,
        map=game.map,
        placement=team.placement,
        drop=drop,
        contested_by=sorted(contested),
        entries=zone_entries(game, team),
        fights=fights(game, team_id),
        deaths=[Spot(area_at(game.areas, x, z), x, z) for _, x, z in team.deaths],
        kills=sum(1 for h in game.hits if h.kind == "KILL" and h.actor_team == team_id),
        knocks=sum(1 for h in game.hits if h.kind == "KNOCK" and h.actor_team == team_id),
    )


# -- Facts ----------------------------------------------------------------------------------


@dataclass
class Fact:
    id: str
    topic: str  # style, rotation, position, fights, deaths, drops, results
    text: str
    value: float
    n: int  # matches it rests on
    of: int  # matches it could have rested on
    matches: list[int]
    map: str | None = None

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "text": self.text,
            "value": self.value,
            "n": self.n,
            "of": self.of,
            "matches": self.matches,
            "map": self.map,
        }


def _spots(
    spots: Iterable[tuple[Spot, int]],
) -> list[tuple[str, int, list[int], tuple[float, float]]]:
    """Group places: by area name, or unnamed ones by distance. (label, count, matches, xz)."""
    named: dict[str, list[tuple[Spot, int]]] = defaultdict(list)
    loose: list[list[tuple[Spot, int]]] = []
    for spot, match in spots:
        if spot.name:
            named[spot.name].append((spot, match))
            continue
        for group in loose:
            gx = statistics.fmean(s.x for s, _ in group)
            gz = statistics.fmean(s.z for s, _ in group)
            if math.hypot(spot.x - gx, spot.z - gz) <= SPOT_M:
                group.append((spot, match))
                break
        else:
            loose.append([(spot, match)])
    out = []
    for name, items in named.items():
        xz = (statistics.fmean(s.x for s, _ in items), statistics.fmean(s.z for s, _ in items))
        out.append((name, len(items), sorted({m for _, m in items}), xz))
    for items in loose:
        xz = (statistics.fmean(s.x for s, _ in items), statistics.fmean(s.z for s, _ in items))
        label = f"an unnamed spot near ({round(xz[0])}, {round(xz[1])})"
        out.append((label, len(items), sorted({m for _, m in items}), xz))
    return sorted(out, key=lambda s: -s[1])


def _share(k: int, n: int) -> str:
    return f"{k} of {n}"


def team_facts(
    matches: Sequence[TeamMatch], names: dict[int, str] | None = None, *, scope: str | None = None
) -> list[Fact]:
    """Facts about one team from its matches (all maps, or one map when ``scope`` is set)."""
    names = names or {}
    facts: list[Fact] = []
    prefix = f"{scope}:" if scope else ""
    where = f" on {scope.title()}" if scope else ""
    ms = [m for m in matches if scope is None or m.map == scope]
    n = len(ms)
    if n < MIN_MATCHES:
        return facts
    ids = [m.match for m in ms]

    def add(key, topic, text, value, k, of, matches_):
        facts.append(
            Fact(f"{prefix}{key}", topic, text, round(value, 2), k, of, list(matches_), scope)
        )

    # Results
    avg = statistics.fmean(m.placement for m in ms)
    booyahs = [m.match for m in ms if m.placement == 1]
    add(
        "results.placement",
        "results",
        f"Average placement{where}: {avg:.1f} over {n} matches",
        avg,
        n,
        n,
        ids,
    )
    if booyahs:
        add(
            "results.booyah",
            "results",
            f"Booyah in {_share(len(booyahs), n)} matches{where}",
            len(booyahs),
            len(booyahs),
            n,
            booyahs,
        )

    # Style: aggression
    knocks = statistics.fmean(m.knocks for m in ms)
    kills = statistics.fmean(m.kills for m in ms)
    all_fights = [(m.match, f) for m in ms for f in m.fights]
    started = [mid for mid, f in all_fights if f.started]
    per_match = len(all_fights) / n
    start_share = len(started) / len(all_fights) if all_fights else 0.0
    add(
        "style.knocks",
        "style",
        f"{knocks:.1f} knocks and {kills:.1f} kills per match{where}",
        knocks,
        n,
        n,
        ids,
    )
    if all_fights:
        add(
            "style.fights",
            "style",
            f"{per_match:.1f} fights per match{where}, and they made the first knock or kill"
            f" in {round(start_share * 100)}% of them",
            per_match,
            n,
            n,
            ids,
        )
        style = (
            "aggressive"
            if per_match >= 3 and start_share >= 0.55
            else "passive"
            if per_match < 1.5 or start_share < 0.4
            else "balanced"
        )
        add("style.label", "style", f"Playstyle{where}: {style}", per_match, n, n, ids)

    # Rotation timing, per zone
    by_zone: dict[int, list[tuple[int, ZoneEntry]]] = defaultdict(list)
    for m in ms:
        for e in m.entries:
            by_zone[e.zone].append((m.match, e))
    for zone, rows in sorted(by_zone.items()):
        if len(rows) < MIN_MATCHES:
            continue
        late = [mid for mid, e in rows if e.lead_s is None or e.lead_s < 0]
        early = [mid for mid, e in rows if e.lead_s is not None and e.lead_s >= EARLY_S]
        leads = [e.lead_s for _, e in rows if e.lead_s is not None]
        if late:
            add(
                f"rotation.z{zone}.late",
                "rotation",
                f"Got inside Zone {zone} after it closed (or never)"
                f" in {_share(len(late), len(rows))} matches{where}",
                len(late) / len(rows),
                len(late),
                len(rows),
                late,
            )
        if leads:
            med = statistics.median(leads)
            add(
                f"rotation.z{zone}.lead",
                "rotation",
                f"Typically inside Zone {zone} {abs(round(med))} s"
                f" {'before' if med >= 0 else 'after'} it closed{where}",
                med,
                len(leads),
                len(rows),
                [mid for mid, e in rows if e.lead_s is not None],
            )
        if early and len(early) / len(rows) >= 0.6:
            add(
                f"rotation.z{zone}.early",
                "rotation",
                f"Rotated early into Zone {zone} (at least {round(EARLY_S)} s before it closed)"
                f" in {_share(len(early), len(rows))} matches{where}",
                len(early) / len(rows),
                len(early),
                len(rows),
                early,
            )

    # Edge or centre, from Zone 2 on
    edges = [
        (m.match, e.edge)
        for m in ms
        for e in m.entries
        if e.zone >= 2 and e.edge is not None and e.edge <= 1.0
    ]
    if len({mid for mid, _ in edges}) >= MIN_MATCHES:
        avg_edge = statistics.fmean(v for _, v in edges)
        label = (
            "the centre"
            if avg_edge < 0.5
            else "the edge"
            if avg_edge > 0.75
            else "between the centre and the edge"
        )
        used = sorted({mid for mid, _ in edges})
        add(
            "position.edge",
            "position",
            f"Usually holds {label} of the zone when it closes{where}"
            f" (on average {round(avg_edge * 100)}% of the way out from the centre)",
            avg_edge,
            len(used),
            n,
            used,
        )

    # Fights: win rate overall, by zone, by opponent
    if len({mid for mid, _ in all_fights}) >= MIN_MATCHES:
        won = [mid for mid, f in all_fights if f.result == "won"]
        lost = [mid for mid, f in all_fights if f.result == "lost"]
        add(
            "fights.record",
            "fights",
            f"Won {len(won)}, lost {len(lost)} of {len(all_fights)} fights{where}",
            len(won) / len(all_fights),
            len({mid for mid, _ in all_fights}),
            n,
            sorted({mid for mid, _ in all_fights}),
        )
        by_fight_zone: dict[int, list[tuple[int, Fight]]] = defaultdict(list)
        for mid, f in all_fights:
            by_fight_zone[f.zone].append((mid, f))
        for zone, rows in sorted(by_fight_zone.items()):
            if len(rows) < MIN_MATCHES:
                continue
            w = sum(1 for _, f in rows if f.result == "won")
            lo = sum(1 for _, f in rows if f.result == "lost")
            add(
                f"fights.z{zone}",
                "fights",
                f"During Zone {zone}: won {w}, lost {lo} of {len(rows)} fights{where}",
                w / len(rows),
                len({mid for mid, _ in rows}),
                n,
                sorted({mid for mid, _ in rows}),
            )
        by_opp: dict[int, list[tuple[int, Fight]]] = defaultdict(list)
        for mid, f in all_fights:
            by_opp[f.opponent].append((mid, f))
        for opp, rows in sorted(by_opp.items(), key=lambda r: -len(r[1])):
            if len(rows) < MIN_MATCHES:
                continue
            w = sum(1 for _, f in rows if f.result == "won")
            lo = sum(1 for _, f in rows if f.result == "lost")
            add(
                f"fights.vs{opp}",
                "fights",
                f"Against {names.get(opp, f'team {opp}')}:"
                f" won {w}, lost {lo} of {len(rows)} fights{where}",
                w / len(rows),
                len({mid for mid, _ in rows}),
                n,
                sorted({mid for mid, _ in rows}),
            )

    # Where they die (final deaths only; early respawned deaths don't count)
    deaths = [(s, m.match) for m in ms for s in m.deaths]
    for i, (label, count, mids, _) in enumerate(_spots(deaths)[:3]):
        if len(mids) < 2:
            break
        add(
            f"deaths.top{i + 1}",
            "deaths",
            f"{count} player deaths at {label}{where}, in {_share(len(mids), n)} matches",
            count,
            len(mids),
            n,
            mids,
        )

    # Drops (per map only: a drop spot means nothing across maps)
    if scope:
        drops = [(m.drop, m.match) for m in ms if m.drop]
        spots = _spots(drops)
        if spots:
            label, count, mids, _ = spots[0]
            if count >= 2:
                placements = [m.placement for m in ms if m.match in mids]
                add(
                    "drops.usual",
                    "drops",
                    f"Usual drop{where}: {label}, in {_share(count, n)} matches,"
                    f" average placement {statistics.fmean(placements):.1f} from there",
                    count / n,
                    count,
                    n,
                    mids,
                )
        contested = [m.match for m in ms if m.contested_by]
        if contested:
            rivals = Counter(t for m in ms for t in m.contested_by)
            top, times = rivals.most_common(1)[0]
            add(
                "drops.contested",
                "drops",
                f"Drop was contested in {_share(len(contested), n)} matches{where},"
                f" most often by {names.get(top, f'team {top}')} ({times})",
                len(contested) / n,
                len(contested),
                n,
                contested,
            )
    return facts


def profile(matches: Sequence[TeamMatch], names: dict[int, str] | None = None) -> dict:
    """Every fact about a team: all maps together, then each map with enough matches."""
    facts = team_facts(matches, names)
    for map_slug in sorted({m.map for m in matches}):
        facts += team_facts(matches, names, scope=map_slug)
    return {
        "matches": len(matches),
        "maps": dict(Counter(m.map for m in matches)),
        "facts": [f.as_dict() for f in facts],
    }


# -- Loading from the database --------------------------------------------------------------


def load_games(match_ids: Iterable[int] | None = None) -> list[Game]:
    """Published matches as ``Game``s (or just ``match_ids``)."""
    from apps.league.models import Match
    from apps.maps.models import MapArea
    from apps.results.models import MatchEvent, TeamMatchResult, ZonePhase
    from apps.rotations.paths import match_paths, zone_close_times

    qs = Match.objects.filter(status=Match.Status.PUBLISHED).select_related("map", "match_day")
    if match_ids is not None:
        qs = qs.filter(pk__in=list(match_ids))
    areas_by_map: dict[int, list[Area]] = defaultdict(list)
    for a in MapArea.objects.all():
        areas_by_map[a.map_id].append(Area(a.name, a.polygon))

    K = MatchEvent.Kind
    games = []
    for match in qs:
        closes = zone_close_times(match)
        first_phase: dict[int, ZonePhase] = {}
        for p in ZonePhase.objects.filter(match=match, game_time_s__isnull=False).order_by(
            "game_time_s"
        ):
            first_phase.setdefault(p.stage_index, p)
        shrink_stages = sorted(
            {
                p.stage_index
                for p in ZonePhase.objects.filter(
                    match=match, state=ZonePhase.State.SHRINK, game_time_s__isnull=False
                )
            }
        )
        zones = [
            Zone(
                i + 1,
                first_phase[s].inner_x,
                first_phase[s].inner_z,
                first_phase[s].inner_radius,
                first_phase[s].game_time_s,
                close,
            )
            for i, (s, close) in enumerate(zip(shrink_stages, closes, strict=False))
        ]

        events = list(MatchEvent.objects.filter(match=match, game_time_s__isnull=False))
        hits = [
            Hit(
                e.game_time_s,
                e.kind,
                e.actor_team_id,
                e.target_team_id,
                e.target_entity,
                e.tx,
                e.tz,
            )
            for e in events
            if e.kind in (K.KILL, K.KNOCK) and e.actor_team_id and e.target_team_id
        ]
        respawns: dict[int, list[float]] = defaultdict(list)
        for e in events:
            if e.kind == K.RESPAWN and e.actor_entity:
                respawns[e.actor_entity].append(e.game_time_s)
        deaths: dict[int, list[tuple[float, float, float]]] = defaultdict(list)
        for e in events:
            if e.kind != K.DEATH or e.x is None or not e.actor_team_id:
                continue
            if any(t > e.game_time_s for t in respawns.get(e.actor_entity, [])):
                continue  # came back: an early-game respawn
            deaths[e.actor_team_id].append((e.game_time_s, e.x, e.z))

        paths = match_paths(match)
        teams = {
            r.team_id: TeamGame(
                r.team_id,
                r.placement,
                r.eliminated_at_s,
                paths.get(r.team_id),
                deaths.get(r.team_id, []),
            )
            for r in TeamMatchResult.objects.filter(match=match)
        }
        label = f"{match.match_day} M{match.number}"
        games.append(
            Game(
                match.pk,
                label,
                match.map.slug if match.map else "unknown",
                zones,
                hits,
                teams,
                areas_by_map.get(match.map_id, []),
            )
        )
    return games


def team_profile(team_id: int, games: Sequence[Game] | None = None) -> dict:
    from apps.league.models import Team

    games = load_games() if games is None else games
    played = [measure(g, team_id) for g in games if team_id in g.teams]
    names = dict(Team.objects.values_list("pk", "name"))
    out = profile(played, names)
    out["match_labels"] = {g.match: g.label for g in games if team_id in g.teams}
    return out
