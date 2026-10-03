"""A team's real path through a match, from the replay's player tracks.

Each player's track (``PlayerTrack``: world decimetres every 0.5 s, ``None`` where the
feed has a hole) is used from the moment that player lands. At every step, the team's
centre is the average of its players who are on the ground and alive. Short holes are
bridged in a straight line (no detours are invented); a longer hole splits the path.
The centre is smoothed to remove jitter, then simplified so it stays light on phones.

Zone, drop and end markers are read off the same path, so they sit on the line.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from apps.league.models import Match
from apps.results.models import ZonePhase

from .models import MAX_ZONES, PlayerTrack

# Gliding down is ~25-30 m/s across the map, running ~5 m/s: a player has landed once
# they cover less than this over the next couple of seconds.
LANDED_SPEED = 12.0  # metres (world units) per second
LANDED_WINDOW_S = 2.0
# Only the start of a track can be a parachute (it begins at the jump).
LANDING_SEARCH_S = 150.0
MAX_BRIDGE_S = 10.0  # a hole up to this long is joined with a straight line
SMOOTH_S = 3.0  # moving-average window
SIMPLIFY_M = 2.0  # largest error simplification may add, in metres
GROUP_M = 120.0  # players this close together move as one group
FIRST_DROP_S = 30.0  # tracks starting this long after the first one are respawn drops
# Nobody covers this much in one step (vehicles do ~15 m): a bigger jump means the group
# the line followed is gone and the rest of the team is elsewhere, so the line breaks
# instead of drawing a straight line nobody walked.
MAX_JUMP_M = 150.0
MIN_SEGMENT = 4  # shorter pieces (2 s) are noise

Point = tuple[float, float, float]  # t, x, z (seconds, world units)


@dataclass
class Track:
    start_s: float
    step_s: float
    points: Sequence[Sequence[int] | None]  # world decimetres


@dataclass
class TeamPath:
    segments: list[list[Point]]  # smoothed, not simplified
    landed_s: float | None  # when the whole team was down

    @property
    def end(self) -> Point | None:
        return self.segments[-1][-1] if self.segments else None

    def at(self, t: float) -> Point | None:
        """The team's position at ``t``, or None outside the path or inside a hole."""
        for seg in self.segments:
            if seg[0][0] <= t <= seg[-1][0]:
                for a, b in zip(seg, seg[1:], strict=False):
                    if a[0] <= t <= b[0]:
                        k = 0.0 if b[0] == a[0] else (t - a[0]) / (b[0] - a[0])
                        return (t, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k)
                return seg[0]
        return None

    def simplified(self, tolerance: float = SIMPLIFY_M) -> list[list[list[float]]]:
        """``[[t, x, z], ...]`` per segment, rounded, with redundant points dropped."""
        return [
            [[round(t, 1), round(x, 1), round(z, 1)] for t, x, z in simplify(seg, tolerance)]
            for seg in self.segments
        ]


def landed_index(track: Track) -> int:
    """Index of the first step where the player is on the ground (0 if never seen gliding)."""
    pts = track.points
    ahead = max(1, round(LANDED_WINDOW_S / track.step_s))
    limit = min(len(pts), round(LANDING_SEARCH_S / track.step_s))
    for i in range(limit):
        a = pts[i]
        b = pts[i + ahead] if i + ahead < len(pts) else None
        if a is None or b is None:
            continue
        dist = math.hypot(b[0] - a[0], b[1] - a[1]) / 10
        if dist / (ahead * track.step_s) < LANDED_SPEED:
            return i
    return 0


def bridged(
    points: Sequence[Sequence[int] | None], max_steps: int
) -> list[tuple[float, float] | None]:
    """World-unit points with holes of up to ``max_steps`` filled in a straight line."""
    out: list[tuple[float, float] | None] = [
        (p[0] / 10, p[1] / 10) if p is not None else None for p in points
    ]
    last = None
    for i, p in enumerate(out):
        if p is None:
            continue
        if last is not None and 1 < i - last <= max_steps + 1:
            a, b = out[last], p
            for j in range(last + 1, i):
                k = (j - last) / (i - last)
                out[j] = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
        last = i
    return out


def _group_centre(
    positions: list[tuple[float, float]], previous: tuple[float, float] | None
) -> tuple[float, float]:
    """Average of the group the line is following: the players within ``GROUP_M`` of the
    one nearest where the team just was. At the start, or once that group is gone, the
    biggest group. A player split off from the rest doesn't drag the line to an empty spot
    between them, and the line doesn't hop back and forth between two groups."""
    if len(positions) == 1:
        return positions[0]

    def near(a):
        return [b for b in positions if math.hypot(a[0] - b[0], a[1] - b[1]) <= GROUP_M]

    def dist(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    anchor = min(positions, key=lambda a: dist(a, previous)) if previous else None
    if anchor is None or dist(anchor, previous) > GROUP_M:
        anchor = max(positions, key=lambda a: len(near(a)))
    group = near(anchor)
    return (sum(p[0] for p in group) / len(group), sum(p[1] for p in group) / len(group))


def team_path(tracks: Iterable[Track]) -> TeamPath:
    tracks = [t for t in tracks if t.points]
    if not tracks:
        return TeamPath([], None)
    step = tracks[0].step_s
    max_steps = round(MAX_BRIDGE_S / step)
    # The team is down once everyone in the first drop has landed (a respawn drops later).
    first_drop = min(t.start_s for t in tracks) + FIRST_DROP_S
    at_step: dict[int, list[tuple[float, float]]] = {}
    landings = []
    for track in tracks:
        first = landed_index(track)
        offset = round(track.start_s / step)
        if track.start_s <= first_drop:
            landings.append(track.start_s + first * step)
        for i, p in enumerate(bridged(track.points, max_steps)):
            if i >= first and p is not None:
                at_step.setdefault(offset + i, []).append(p)
    landed = max(landings) if landings else None
    start = round(landed / step) if landed is not None else None

    segments: list[list[Point]] = []
    previous: tuple[int, tuple[float, float]] | None = None
    for k in sorted(at_step):
        if start is not None and k < start:
            continue
        centre = _group_centre(at_step[k], previous[1] if previous else None)
        jumped = previous is not None and (
            k - previous[0] > 1
            or math.hypot(centre[0] - previous[1][0], centre[1] - previous[1][1]) > MAX_JUMP_M
        )
        if previous is None or jumped:
            segments.append([])
        segments[-1].append((round(k * step, 3), centre[0], centre[1]))
        previous = (k, centre)
    window = max(1, round(SMOOTH_S / step))
    kept = [smooth(s, window) for s in segments if len(s) >= MIN_SEGMENT]
    return TeamPath(kept, landed)


def smooth(points: list[Point], window: int) -> list[Point]:
    """Centred moving average of x and z; the ends keep their real positions."""
    if len(points) <= 2 or window <= 1:
        return points
    half = window // 2
    xs = [p[1] for p in points]
    zs = [p[2] for p in points]
    out = [points[0]]
    for i in range(1, len(points) - 1):
        lo, hi = max(0, i - half), min(len(points), i + half + 1)
        n = hi - lo
        out.append((points[i][0], sum(xs[lo:hi]) / n, sum(zs[lo:hi]) / n))
    out.append(points[-1])
    return out


def simplify(points: list[Point], tolerance: float) -> list[Point]:
    """Ramer-Douglas-Peucker on x/z: keeps the shape within ``tolerance`` world units."""
    if len(points) <= 2:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        ax, az = points[a][1], points[a][2]
        bx, bz = points[b][1], points[b][2]
        dx, dz = bx - ax, bz - az
        length = math.hypot(dx, dz)
        worst, index = -1.0, -1
        for i in range(a + 1, b):
            px, pz = points[i][1], points[i][2]
            if length == 0:
                d = math.hypot(px - ax, pz - az)
            else:
                d = abs(dx * (az - pz) - dz * (ax - px)) / length
            if d > worst:
                worst, index = d, i
        if worst > tolerance:
            keep[index] = True
            stack += [(a, index), (index, b)]
    return [p for p, k in zip(points, keep, strict=True) if k]


def zone_close_times(match: Match) -> list[float]:
    """Game second each zone (1, 2, ...) finished closing.

    A zone has closed when the next stage begins (its first logged phase); the last zone
    of the match, with no next stage, closes when its shrink is logged plus nothing: we
    then use its shrink start.
    """
    phases = list(
        ZonePhase.objects.filter(match=match, game_time_s__isnull=False).values_list(
            "stage_index", "state", "game_time_s"
        )
    )
    shrinks = sorted((s, t) for s, state, t in phases if state == ZonePhase.State.SHRINK)
    out = []
    for stage, start in shrinks[:MAX_ZONES]:
        later = [t for s, _, t in phases if s > stage and t >= start]
        out.append(min(later) if later else start)
    return out


def match_paths(match: Match) -> dict[int, TeamPath]:
    """Every team's path in a match, keyed by team id (teams without tracks are left out)."""
    by_team: dict[int, list[Track]] = {}
    for row in PlayerTrack.objects.filter(match=match, team__isnull=False).only(
        "team_id", "start_s", "step_s", "points"
    ):
        by_team.setdefault(row.team_id, []).append(Track(row.start_s, row.step_s, row.points))
    paths = {team: team_path(tracks) for team, tracks in by_team.items()}
    return {team: p for team, p in paths.items() if p.segments}
