"""A team's real route through a match, from its players' replay tracks.

The route follows the team's centre (the average position of its players still in the
feed) from the moment they land until they are eliminated or the match ends:

* A player counts from when they land (their speed drops to walking pace after the
  parachute), so the plane and the glide don't drag the line across the map.
* The centre is smoothed over a few seconds to take out jitter.
* A gap shorter than ``BRIDGE_S`` (nobody in the feed for a moment) is bridged with a
  straight line; a longer one breaks the route into separate pieces instead of
  inventing a path nobody took.
* Each piece is simplified (Ramer-Douglas-Peucker) so it keeps its shape within
  ``SIMPLIFY_M`` metres but needs far fewer points, which keeps pages light on phones.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .models import PlayerTrack

LANDED_SPEED = 9.0  # m/s: gliding is 13-50, running and driving off-road stay under this
LANDED_WINDOW_S = 2.0  # speed is measured over this long, twice in a row
BRIDGE_S = 20.0
SMOOTH_S = 2.0  # each point averages this many seconds either side
SIMPLIFY_M = 1.5


@dataclass
class TeamPath:
    """The smoothed route: ``pieces`` of ``(t, x, z)`` in seconds and metres."""

    pieces: list[list[tuple[float, float, float]]] = field(default_factory=list)

    @property
    def start(self) -> tuple[float, float, float] | None:
        return self.pieces[0][0] if self.pieces else None

    @property
    def end(self) -> tuple[float, float, float] | None:
        return self.pieces[-1][-1] if self.pieces else None

    def at(self, t: float) -> tuple[float, float, float] | None:
        """Where the team was at ``t`` (on the route), or None outside it or in a break."""
        for piece in self.pieces:
            if piece[0][0] <= t <= piece[-1][0]:
                lo, hi = 0, len(piece) - 1
                while hi - lo > 1:
                    mid = (lo + hi) // 2
                    if piece[mid][0] <= t:
                        lo = mid
                    else:
                        hi = mid
                a, b = piece[lo], piece[hi]
                k = 0.0 if b[0] == a[0] else (t - a[0]) / (b[0] - a[0])
                return (t, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k)
        return None

    def simplified(self, tolerance: float = SIMPLIFY_M) -> list[list[list[int]]]:
        """The route for the website: pieces of ``[x, z]`` in world decimetres."""
        return [
            [[round(x * 10), round(z * 10)] for _t, x, z in simplify(piece, tolerance)]
            for piece in self.pieces
        ]


def landed_index(points: list, step: float) -> int | None:
    """Index of the first sample where the player is on foot (or None: never landed)."""
    n = max(1, round(LANDED_WINDOW_S / step))

    def slow(i: int) -> bool:
        a, b = points[i], points[i + n] if i + n < len(points) else None
        return a is not None and b is not None and math.dist(a, b) / 10 / (n * step) < LANDED_SPEED

    for i, p in enumerate(points):
        if p is None:
            continue
        if i + n >= len(points):
            return i  # the track ends here: whatever this is, it's the last we know
        if slow(i) and (i + 2 * n >= len(points) or slow(i + n)):
            return i
    return None


def team_path(
    tracks: list[PlayerTrack], *, until_s: float | None = None, step: float | None = None
) -> TeamPath:
    """The team's route from its players' tracks, cut at ``until_s`` (its elimination)."""
    if not tracks:
        return TeamPath()
    step = step or tracks[0].step_s
    # Every player's landed positions on one shared time grid (index = time / step).
    players: list[dict[int, tuple[float, float]]] = []
    landings: list[int] = []
    for track in tracks:
        land = landed_index(track.points, track.step_s)
        if land is None:
            continue
        first = round(track.start_s / step)
        positions = {
            first + i: (p[0] / 10, p[1] / 10)
            for i, p in enumerate(track.points)
            if i >= land and p is not None
        }
        if until_s is not None:
            last = math.floor(until_s / step)
            positions = {k: v for k, v in positions.items() if k <= last}
        if positions:
            players.append(positions)
            landings.append(first + land)
    if not players:
        return TeamPath()

    # The route starts once half the team is down, so one early lander doesn't set it.
    landings.sort()
    begin = landings[(len(landings) - 1) // 2]
    end = max(max(p) for p in players)
    centre: dict[int, tuple[float, float]] = {}
    for k in range(begin, end + 1):
        here = [p[k] for p in players if k in p]
        if here:
            centre[k] = (sum(x for x, _ in here) / len(here), sum(z for _, z in here) / len(here))
    if not centre:
        return TeamPath()

    # Split at long gaps; bridge short ones in a straight line.
    bridge = round(BRIDGE_S / step)
    keys = sorted(centre)
    runs: list[list[int]] = [[keys[0]]]
    for k in keys[1:]:
        if k - runs[-1][-1] > bridge:
            runs.append([k])
        else:
            runs[-1].append(k)
    half = max(1, round(SMOOTH_S / step))
    pieces = []
    for run in runs:
        filled = _fill(run, centre)
        pieces.append(
            [
                (k * step, x, z)
                for k, (x, z) in zip(range(run[0], run[-1] + 1), _smooth(filled, half), strict=True)
            ]
        )
    return TeamPath(pieces)


def _fill(run: list[int], centre: dict[int, tuple[float, float]]) -> list[tuple[float, float]]:
    """Every grid step from the run's first to last key; holes interpolated linearly."""
    out: list[tuple[float, float]] = []
    for a, b in zip(run, run[1:], strict=False):
        (ax, az), (bx, bz) = centre[a], centre[b]
        for i in range(b - a):
            k = i / (b - a)
            out.append((ax + (bx - ax) * k, az + (bz - az) * k))
    out.append(centre[run[-1]])
    return out


def _smooth(points: list[tuple[float, float]], half: int) -> list[tuple[float, float]]:
    """Centred moving average; the window shrinks at the ends so they stay put."""
    n = len(points)
    sx = [0.0]
    sz = [0.0]
    for x, z in points:
        sx.append(sx[-1] + x)
        sz.append(sz[-1] + z)
    out = []
    for i in range(n):
        w = min(half, i, n - 1 - i)
        lo, hi = i - w, i + w + 1
        out.append(((sx[hi] - sx[lo]) / (hi - lo), (sz[hi] - sz[lo]) / (hi - lo)))
    return out


def simplify(points: list[tuple], tolerance: float) -> list[tuple]:
    """Ramer-Douglas-Peucker on ``(t, x, z)``: drop points within ``tolerance`` metres."""
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        _, ax, az = points[first]
        _, bx, bz = points[last]
        dx, dz = bx - ax, bz - az
        length2 = dx * dx + dz * dz
        worst, index = -1.0, -1
        for i in range(first + 1, last):
            _, px, pz = points[i]
            # Distance to the segment (not the whole line), so a run out and back along
            # the same line still counts as a detour.
            k = (
                0.0
                if length2 == 0
                else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / length2))
            )
            d = math.hypot(px - (ax + dx * k), pz - (az + dz * k))
            if d > worst:
                worst, index = d, i
        if worst > tolerance:
            keep[index] = True
            stack.append((first, index))
            stack.append((index, last))
    return [p for p, k in zip(points, keep, strict=True) if k]
