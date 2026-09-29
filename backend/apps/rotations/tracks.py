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

from .models import PlayerTrack, ReplayObject

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


UAV_STEP_S = 0.5  # a UAV path keeps one point per half second
# How far a Bolt Maker reaches: strikes land at random inside the zone (patch notes), and
# in every zone of the Day 11 replays they land up to 76-81 m from the centre, so the
# zone is drawn with an 80 m radius (160 m across).
BOLT_ZONE_M = 80.0


def build_objects(
    match: Match,
    data: bytes,
    entity_uid: dict[int, int],
    players: dict[int, Player],
    uid_team: dict[int, Team],
) -> int:
    """Replace the match's UAVs and Bolt Makers with those in ``data``. Returns the count."""
    ReplayObject.objects.filter(match=match).delete()
    found = replay_bin.parse_objects(data)
    rows = []

    def owned(entity: int | None) -> dict:
        uid = entity_uid.get(entity) if entity else None
        return {"owner_entity": entity, "player": players.get(uid), "team": uid_team.get(uid)}

    for drone in found["drones"]:
        samples = drone["samples"]
        points, last = [], None
        for i, (t, x, _y, z) in enumerate(samples):
            if last is None or t - last >= UAV_STEP_S - 0.01 or i == len(samples) - 1:
                points.append([round(t, 1), round(x * 10), round(z * 10)])
                last = t
        kind = (
            ReplayObject.Kind.PLAYER_UAV
            if drone["kind"] == "PLAYER_UAV"
            else ReplayObject.Kind.GENERAL_UAV
        )
        rows.append(
            ReplayObject(
                match=match,
                kind=kind,
                start_s=samples[0][0],
                end_s=samples[-1][0],
                x=samples[0][1],
                z=samples[0][3],
                radius_m=drone["range"],
                points=points,
                **owned(drone["owner"]),
            )
        )
    for bolt in found["bolts"]:
        strikes = bolt["strikes"]
        rows.append(
            ReplayObject(
                match=match,
                kind=ReplayObject.Kind.BOLT_MAKER,
                start_s=bolt["t"],
                end_s=max([bolt["t"] + bolt["duration"], *(s[0] for s in strikes)]),
                x=bolt["x"],
                z=bolt["z"],
                radius_m=BOLT_ZONE_M,
                points=[[round(t, 1), round(x * 10), round(z * 10)] for t, x, z, _r in strikes],
                **owned(bolt["owner"]),
            )
        )
    ReplayObject.objects.bulk_create(rows)
    return len(rows)
