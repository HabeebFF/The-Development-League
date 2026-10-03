"""Team routes from replay tracks: landing, centre, gaps, smoothing and simplifying."""

import math

import pytest

from apps.results.models import TeamMatchResult
from apps.rotations.auto import draft_rotations
from apps.rotations.models import PlayerTrack, TeamRotation
from apps.rotations.paths import landed_index, simplify, team_path

from .test_rotations import match  # noqa: F401  (fixture)

STEP = 0.5


def walk(start_s, glide_s, until_s, z_dm=0, x0_dm=0, gaps=()):
    """A track: glide east at 30 m/s for ``glide_s``, then walk east at 2 m/s.

    ``gaps`` are (from_s, to_s) where the player is missing from the feed."""
    points, x = [], x0_dm
    t = start_s
    while t <= until_s + 1e-9:
        x += 150 if t - start_s < glide_s else 10
        missing = any(a <= t < b for a, b in gaps)
        points.append(None if missing else [x, z_dm])
        t += STEP
    return PlayerTrack(entity_id=len(points), start_s=start_s, step_s=STEP, points=points)


def test_landing_skips_the_glide():
    track = walk(50, 10, 80)
    i = landed_index(track.points, STEP)
    assert 18 <= i <= 21  # ~10 s of gliding at 0.5 s a sample
    assert landed_index([None, None], STEP) is None


def test_route_follows_the_team_centre_from_landing():
    a = walk(50, 10, 200, z_dm=0)
    b = walk(50, 10, 200, z_dm=200)  # 20 m to the side
    path = team_path([a, b])
    (piece,) = path.pieces
    t0, x0, z0 = piece[0]
    assert 59 <= t0 <= 61  # starts where they landed, not on the plane
    assert z0 == pytest.approx(10.0)  # halfway between the two players
    assert all(z == pytest.approx(10.0) for _t, _x, z in piece)
    assert piece[-1][0] == 200
    # Walking 2 m/s in a straight line: the simplified route is just its two ends.
    assert len(path.simplified()) == 1 and len(path.simplified()[0]) == 2
    assert path.at(150)[1] == pytest.approx(x0 + 2 * (150 - t0), abs=0.5)


def test_short_gaps_are_bridged_and_long_ones_break_the_route():
    short = walk(50, 10, 300, gaps=[(100, 110)])
    assert len(team_path([short]).pieces) == 1
    long = walk(50, 10, 300, gaps=[(100, 160)])
    pieces = team_path([long]).pieces
    assert len(pieces) == 2
    assert team_path([long]).at(130) is None  # nothing invented inside the break
    # A teammate still in the feed keeps the route whole.
    assert len(team_path([long, walk(50, 10, 300, z_dm=50)]).pieces) == 1


def test_route_stops_at_elimination_and_jitter_is_smoothed():
    track = walk(50, 10, 300)
    for i in range(40, len(track.points), 2):  # +-1.5 m zigzag on every other sample
        track.points[i] = [track.points[i][0], 15]
    path = team_path([track], until_s=250)
    assert path.end[0] == 250
    assert max(abs(z) for _t, _x, z in path.pieces[0][10:-10]) < 1.0


def test_simplify_keeps_shape_and_detours():
    line = [(i, float(i), 0.0) for i in range(100)]
    assert simplify(line, 1.5) == [line[0], line[-1]]
    # Out 30 m and back along the same line: the turn is kept.
    out_back = [(i, float(i), 0.0) for i in range(30)] + [
        (30 + i, 30.0 - i, 0.0) for i in range(31)
    ]
    kept = simplify(out_back, 1.5)
    assert max(x for _t, x, _z in kept) == 30.0
    corner = [(i, float(min(i, 50)), float(max(0, i - 50))) for i in range(101)]
    assert len(simplify(corner, 1.5)) == 3


@pytest.mark.django_db
def test_draft_puts_points_on_the_replay_route(match):  # noqa: F811
    alpha = TeamMatchResult.objects.get(match=match, team__name="Alpha").team
    bravo = TeamMatchResult.objects.get(match=match, team__name="Bravo").team
    for z in (0, 100):
        track = walk(50, 10, 700, z_dm=z)
        track.match, track.team, track.entity_id = match, alpha, 1000 + z
        track.save()
    track = walk(50, 10, 470, z_dm=-500)
    track.match, track.team, track.entity_id = match, bravo, 2000
    track.save()

    draft_rotations(match)
    rotation = TeamRotation.objects.get(match=match, team=alpha)
    assert rotation.path and len(rotation.path[0]) == 2  # a straight walk: two points
    points = list(rotation.points.all())
    # Zones shrink at 200, 400 and 600 s: each closes when the next starts (the last
    # one about a minute later).
    assert [(p.checkpoint, p.game_time_s) for p in points][1:] == [
        ("ZONE_1", 400),
        ("ZONE_2", 600),
        ("ZONE_3", 660),
        ("FINAL", 700),
    ]
    for p in points:
        assert p.z == pytest.approx(5.0) and p.evidence == {"replay": 1}
    zone1 = points[1]
    assert math.isclose(zone1.x, points[0].x + 2 * (400 - points[0].game_time_s), abs_tol=0.5)

    # Bravo is out at 450 s: its route ends there and it has no zone 2 or 3 dot.
    bravo_points = TeamRotation.objects.get(match=match, team=bravo).points.all()
    assert [p.checkpoint for p in bravo_points] == ["DROP", "ZONE_1", "ELIMINATED"]
    assert bravo_points.last().game_time_s == 452  # elimination + slack

    # Staff edits keep their points, but the route is still refreshed.
    rotation.status = TeamRotation.Status.CONFIRMED
    rotation.path = []
    rotation.save()
    draft_rotations(match)
    rotation.refresh_from_db()
    assert rotation.path and rotation.status == "CONFIRMED"
