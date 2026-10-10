"""After-scrim review: the moments in a match that cost a team the most (and its best one).

Read straight from what the logs recorded: every knock and kill, every player's position
(``PlayerTrack``, every 0.5 s) and the zones. Each moment has a game time, so the website
can open the live replay a few seconds before it.

The checks, for each time one of the team's players goes down:

- **Third party:** a third team knocks them while the team is fighting someone else.
- **Alone:** no standing teammate within ``ALONE_M``.
- **Caught rotating:** moving, and outside the zone being played.
- **Not traded:** a teammate was close, but nobody knocked the attackers back within
  ``TRADE_S``.

Plus late zone entries (from the engine) and, on the good side, fights won and clean
trades. Like the rest of the coach, it is plain arithmetic; no AI.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from apps.rotations.paths import Track

from .engine import FIGHT_GAP_S, Game, Hit, fights, zone_at, zone_entries

# Bump when the rules change, so stored reviews are rebuilt.
RULES = "moments-v1"

ALONE_M = 60.0  # no standing teammate this close: the player was alone
TRADE_S = 10.0  # a knock back on the attackers this soon counts as a trade
SAME_DOWN_S = 45.0  # a knock then a kill on the same player within this is one down
DOWNED_S = 30.0  # a teammate knocked this recently isn't standing
MOVING_M = 12.0  # covered this much in the 5 s before going down: on the move
WIPE_S = 60.0  # the team was wiped this soon after: the moment led to it
MERGE_S = 20.0  # the same kind of moment against the same team this close is one moment
LEAD_S = 8.0  # the replay opens this long before the moment
MAX_BAD = 3
MAX_GOOD = 1

SEVERITY = {"third_party": 3.0, "alone": 3.0, "rotating": 2.5, "untraded": 2.0, "zone": 2.0}


@dataclass
class Player:
    team: int
    name: str
    track: Track | None = None


@dataclass
class Down:
    t: float
    victim: int
    team: int
    by: int  # attacking team
    x: float | None
    z: float | None


@dataclass
class Moment:
    kind: str
    good: bool
    t: float
    title: str
    detail: str
    severity: float = 0.0
    players: list[str] = field(default_factory=list)
    opponent: int | None = None

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "good": self.good,
            "t": round(self.t, 1),
            "clock": clock(self.t),
            "watch_s": round(max(0.0, self.t - LEAD_S), 1),
            "title": self.title,
            "detail": self.detail,
            "players": self.players,
            "opponent": self.opponent,
        }


def clock(s: float) -> str:
    s = max(0, round(s))
    return f"{s // 60}:{s % 60:02d}"


def position(track: Track | None, t: float, window_s: float = 2.0) -> tuple[float, float] | None:
    """Where a player was at ``t`` (metres), from the nearest sample within ``window_s``."""
    if track is None or not track.points:
        return None
    i = round((t - track.start_s) / track.step_s)
    reach = max(1, round(window_s / track.step_s))
    for d in range(reach + 1):
        for j in (i - d, i + d):
            if 0 <= j < len(track.points) and track.points[j] is not None:
                p = track.points[j]
                return p[0] / 10, p[1] / 10
    return None


def downs(hits: Sequence[Hit]) -> list[Down]:
    """Each time a player went down: their first knock or kill, not the finish after it."""
    last: dict[int, float] = {}
    out = []
    for h in sorted(hits, key=lambda h: h.t):
        if h.target is None or h.actor_team == h.target_team:
            continue
        before = last.get(h.target)
        last[h.target] = h.t
        if before is not None and h.t - before <= SAME_DOWN_S:
            continue
        out.append(Down(h.t, h.target, h.target_team, h.actor_team, h.x, h.z))
    return out


def _names(players: list[str]) -> str:
    if len(players) <= 1:
        return players[0] if players else "A player"
    return ", ".join(players[:-1]) + " and " + players[-1]


def find(
    game: Game,
    team_id: int,
    players: dict[int, Player],
    team_names: dict[int, str],
) -> dict:
    """The team's review of one match: a short summary and its moments, in game order."""
    team = game.teams[team_id]

    def tname(t: int | None) -> str:
        return team_names.get(t, f"team {t}") if t is not None else "another team"

    def pname(entity: int) -> str:
        p = players.get(entity)
        return p.name if p and p.name else "A player"

    all_downs = downs(game.hits)
    ours = [d for d in all_downs if d.team == team_id]
    hits = sorted(game.hits, key=lambda h: h.t)
    mates = [e for e, p in players.items() if p.team == team_id]
    eliminated = team.eliminated_s
    first_zone = game.zones[0].announced_s if game.zones else None

    def standing(entity: int, t: float) -> bool:
        if any(d.victim == entity and t - DOWNED_S <= d.t < t for d in ours):
            return False
        return position(players[entity].track, t, 1.0) is not None

    bad: list[Moment] = []
    good: list[Moment] = []
    for d in ours:
        me = players.get(d.victim)
        here = (d.x, d.z) if d.x is not None and d.z is not None else None
        here = here or position(me.track if me else None, d.t)
        others = [e for e in mates if e != d.victim and standing(e, d.t)]
        gaps = [
            math.hypot(p[0] - here[0], p[1] - here[1])
            for e in others
            if here and (p := position(players[e].track, d.t, 1.0))
        ]
        nearest = min(gaps) if gaps else None
        name = pname(d.victim)

        # Fighting another team in the 30 s before this?
        busy_with = [
            h.target_team if h.actor_team == team_id else h.actor_team
            for h in hits
            if d.t - FIGHT_GAP_S <= h.t < d.t
            and team_id in (h.actor_team, h.target_team)
            and d.by not in (h.actor_team, h.target_team)
        ]
        traded = next(
            (
                h
                for h in hits
                if d.t <= h.t <= d.t + TRADE_S and h.actor_team == team_id and h.target_team == d.by
            ),
            None,
        )
        moving = False
        zone = zone_at(game.zones, d.t)
        outside = False
        if zone and here and first_zone is not None and d.t >= first_zone:
            z = game.zones[zone - 1]
            outside = math.hypot(here[0] - z.x, here[1] - z.z) > z.r
            before = position(me.track if me else None, d.t - 5, 1.0)
            if before:
                moving = math.hypot(here[0] - before[0], here[1] - before[1]) >= MOVING_M

        if busy_with:
            rival = busy_with[-1]
            bad.append(
                Moment(
                    "third_party",
                    False,
                    d.t,
                    f"Third-partied by {tname(d.by)}",
                    f"{{who}} went down to {tname(d.by)} while you were fighting {tname(rival)}.",
                    SEVERITY["third_party"],
                    [name],
                    d.by,
                )
            )
        elif nearest is not None and nearest > ALONE_M:
            bad.append(
                Moment(
                    "alone",
                    False,
                    d.t,
                    "Caught alone",
                    f"{{who}} went down to {tname(d.by)}, {round(nearest)} m from the nearest "
                    "teammate.",
                    SEVERITY["alone"],
                    [name],
                    d.by,
                )
            )
        elif outside and moving and zone >= 2:  # Zone 1 is often still loot time
            bad.append(
                Moment(
                    "rotating",
                    False,
                    d.t,
                    f"Caught rotating into Zone {zone}",
                    f"{{who}} went down to {tname(d.by)} while moving outside the safe zone.",
                    SEVERITY["rotating"],
                    [name],
                    d.by,
                )
            )
        elif traded is None and nearest is not None:
            bad.append(
                Moment(
                    "untraded",
                    False,
                    d.t,
                    "Knock not traded",
                    f"{{who}} went down to {tname(d.by)} with a teammate {round(nearest)} m "
                    f"away, and nobody knocked them back within {round(TRADE_S)} s.",
                    SEVERITY["untraded"],
                    [name],
                    d.by,
                )
            )
        elif traded is not None and nearest is not None:
            good.append(
                Moment(
                    "trade",
                    True,
                    d.t,
                    "Quick trade",
                    f"{{who}} went down to {tname(d.by)} and you knocked one of them back "
                    f"{round(traded.t - d.t)} s later.",
                    1.0,
                    [name],
                    d.by,
                )
            )

    # Late into a zone (Zone 2 onwards; Zone 1 is often still loot time).
    for entry in zone_entries(game, team):
        if entry.zone < 2 or (entry.lead_s is not None and entry.lead_s >= 0):
            continue
        z = game.zones[entry.zone - 1]
        if entry.lead_s is None:
            detail = f"Still outside Zone {entry.zone} when it closed."
            t = z.closes_s
        else:
            detail = f"Got inside {round(-entry.lead_s)} s after Zone {entry.zone} closed."
            t = z.closes_s
        bad.append(
            Moment("zone", False, t, f"Late into Zone {entry.zone}", detail, SEVERITY["zone"])
        )

    for f in fights(game, team_id):
        if f.result == "won" and f.downs_for >= 2:
            good.append(
                Moment(
                    "fight_won",
                    True,
                    f.t,
                    f"Won the fight against {tname(f.opponent)}",
                    f"{f.downs_for} downs to {f.downs_against}"
                    + (f" at {f.place}." if f.place else "."),
                    float(f.downs_for - f.downs_against) + 1.0,
                    [],
                    f.opponent,
                )
            )

    bad = _merge(bad)
    for m in bad:
        if eliminated is not None and 0 <= eliminated - m.t <= WIPE_S:
            m.severity += 1.0
            gap = round(eliminated - m.t)
            m.detail += (
                " The team was wiped right after."
                if gap < 3
                else f" The team was wiped {gap} s later."
            )
    for m in bad + good:
        m.detail = m.detail.replace("{who}", _names(m.players))

    picked = sorted(bad, key=lambda m: (-m.severity, m.t))[:MAX_BAD]
    picked += sorted(good, key=lambda m: (-m.severity, m.t))[:MAX_GOOD]
    picked.sort(key=lambda m: m.t)

    wiped_by = None
    if eliminated is not None:
        last = [h for h in hits if h.target_team == team_id and h.t <= eliminated + 1]
        wiped_by = last[-1].actor_team if last else None
    return {
        "placement": team.placement,
        "kills": team.kills
        if team.kills is not None
        else sum(1 for h in hits if h.kind == "KILL" and h.actor_team == team_id),
        "downs_taken": len(ours),
        "eliminated_s": eliminated,
        "eliminated_clock": clock(eliminated) if eliminated is not None else None,
        "wiped_by": tname(wiped_by) if wiped_by is not None else None,
        "moments": [m.as_dict() for m in picked],
    }


def _merge(moments: list[Moment]) -> list[Moment]:
    """Same kind, same opponent, close together: one moment naming every player."""
    out: list[Moment] = []
    for m in sorted(moments, key=lambda m: m.t):
        prev = next(
            (
                o
                for o in reversed(out)
                if o.kind == m.kind and o.opponent == m.opponent and m.t - o.t <= MERGE_S
            ),
            None,
        )
        if prev is None or m.kind == "zone":
            out.append(m)
            continue
        prev.players += [p for p in m.players if p not in prev.players]
        prev.severity += 1.0
        if prev.kind == "alone":
            prev.title = f"{len(prev.players)} players caught alone"
            prev.detail = "{who} each went down away from the rest of the team."
    return out


# -- Loading from the database --------------------------------------------------------------


def review_match(match_id: int) -> dict[int, dict]:
    """Every team's review of one published match, keyed by team id."""
    from apps.league.models import Team
    from apps.results.models import MatchEvent
    from apps.rotations.models import PlayerTrack

    from .engine import load_games

    games = load_games([match_id])
    if not games:
        return {}
    game = games[0]
    players: dict[int, Player] = {}
    for row in PlayerTrack.objects.filter(match_id=match_id, team__isnull=False).select_related(
        "player"
    ):
        players[row.entity_id] = Player(
            row.team_id,
            row.player.display_name if row.player else "",
            Track(row.start_s, row.step_s, row.points),
        )
    # Players the replay feed missed still have a name and team on their knocks.
    for e in MatchEvent.objects.filter(
        match_id=match_id, target_entity__isnull=False, target_team__isnull=False
    ).select_related("target_player"):
        p = players.setdefault(e.target_entity, Player(e.target_team_id, ""))
        if not p.name and e.target_player:
            p.name = e.target_player.display_name
    names = dict(Team.objects.filter(pk__in=list(game.teams)).values_list("pk", "name"))
    out = {}
    for team_id in game.teams:
        review = find(game, team_id, players, names)
        review["has_tracks"] = any(p.track for p in players.values() if p.team == team_id)
        out[team_id] = review
    return out


def save_reviews(match_id: int) -> int:
    """Build and store every team's review of a match (none if it isn't published)."""
    from .models import MatchReview

    reviews = review_match(match_id)
    MatchReview.objects.filter(match_id=match_id).exclude(team_id__in=list(reviews)).delete()
    for team_id, review in reviews.items():
        moments = review.pop("moments")
        MatchReview.objects.update_or_create(
            match_id=match_id,
            team_id=team_id,
            defaults={"rules": RULES, "summary": review, "moments": moments},
        )
    return len(reviews)
