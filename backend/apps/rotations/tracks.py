"""Player tracks for the live replay: parse the replay .bin, resample, store.

Raw samples arrive ~5 times a second at uneven times. They are stored on a fixed grid
(every ``STEP_S`` seconds, linear interpolation between samples) so the website can play
them back with a single index per frame. A gap longer than ``MAX_GAP_S`` (plane, dead,
recording hole) stays empty rather than being drawn as a straight line.
"""

from __future__ import annotations

import math
from bisect import bisect_left

from apps.ingest.parsers import replay_bin
from apps.league.models import Match, Player, Team

from .models import PlayerTrack

STEP_S = 0.5
MAX_GAP_S = 2.5

Sample = tuple[float, float, float, float]  # t, x, y, z


def resample(samples: list[Sample], step: float = STEP_S, max_gap: float = MAX_GAP_S):
    """Return ``(start_s, points)`` with ``points[i]`` at ``start_s + i * step``."""
    if not samples:
        return 0.0, []
    times = [s[0] for s in samples]
    start = math.ceil(times[0] / step) * step
    points: list[list[int] | None] = []
    t = start
    while t <= times[-1] + 1e-9:
        i = bisect_left(times, t)
        if i < len(times) and abs(times[i] - t) < 1e-6:
            a = b = samples[i]
        else:
            a, b = samples[i - 1], samples[min(i, len(samples) - 1)]
        if b[0] - a[0] > max_gap:
            points.append(None)
        else:
            k = 0.0 if b[0] == a[0] else (t - a[0]) / (b[0] - a[0])
            x = a[1] + (b[1] - a[1]) * k
            z = a[3] + (b[3] - a[3]) * k
            points.append([round(x * 10), round(z * 10)])
        t = round(t + step, 6)
    return round(start, 3), points


def build_tracks(
    match: Match,
    data: bytes,
    entity_uid: dict[int, int],
    players: dict[int, Player],
    uid_team: dict[int, Team],
) -> int:
    """Replace the match's tracks with those in ``data``. Returns how many were stored."""
    PlayerTrack.objects.filter(match=match).delete()
    rows = []
    for entity, samples in replay_bin.parse_tracks(data).items():
        start, points = resample(samples)
        if not any(points):
            continue
        uid = entity_uid.get(entity)
        rows.append(
            PlayerTrack(
                match=match,
                entity_id=entity,
                player=players.get(uid),
                team=uid_team.get(uid),
                start_s=start,
                step_s=STEP_S,
                points=points,
            )
        )
    PlayerTrack.objects.bulk_create(rows)
    return len(rows)
