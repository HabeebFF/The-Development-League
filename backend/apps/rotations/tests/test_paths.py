"""Team paths from replay tracks: landing, gaps, groups, smoothing, simplifying, drafts."""

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.rotations.models import PlayerTrack, TeamRotation
from apps.rotations.paths import (
    Track,
    bridged,
    landed_index,
    simplify,
    team_path,
    zone_close_times,
)

from .test_rotations import match  # noqa: F401  (fixture)

STEP = 0.5
pytestmark = pytest.mark.django_db


def glide_then_walk(x0: float, z0: float, glide_steps: int, walk_steps: int, dx: float = 1.0):
    """World decimetres: a glide at 30 m/s along x, then a walk of ``dx`` m per step."""
    pts = [[round((x0 + 15 * i) * 10), round(z0 * 10)] for i in range(glide_steps)]
    x = x0 + 15 * glide_steps
    for _ in range(walk_steps):
        x += dx
        pts.append([round(x * 10), round(z0 * 10)])
    return pts


def test_landing_is_where_the_glide_stops():
    track = Track(60.0, STEP, glide_then_walk(0, 0, glide_steps=20, walk_steps=40))
    assert 16 <= landed_index(track) <= 20
    # A track that starts on the ground (a reconnect) lands at once.
    assert landed_index(Track(60.0, STEP, glide_then_walk(0, 0, 0, 40))) == 0


def test_short_holes_are_bridged_in_a_straight_line_long_ones_stay_open():
    pts = [[0, 0], None, None, [30, 0]] + [None] * 30 + [[100, 0]]
    out = bridged(pts, max_steps=20)
    assert out[1] == (1.0, 0.0) and out[2] == (2.0, 0.0)
    assert out[10] is None and out[-1] == (10.0, 0.0)


def test_simplify_keeps_corners_and_drops_straight_runs():
    line = [(i, float(i), 0.0) for i in range(50)] + [
        (50 + i, 49.0, float(i)) for i in range(1, 50)
    ]
    kept = simplify(line, 0.5)
    assert [(p[1], p[2]) for p in kept] == [(0.0, 0.0), (49.0, 0.0), (49.0, 49.0)]


def test_team_path_follows_the_group_and_not_a_split_off_player():
    together = [Track(100.0, STEP, [[i * 10, 0] for i in range(200)]) for _ in range(3)]
    # The fourth player runs off far to the side: the line stays with the three.
    loner = Track(100.0, STEP, [[i * 10, 5000 + i * 20] for i in range(200)])
    path = team_path([*together, loner])
    assert len(path.segments) == 1
    assert all(abs(z) < 1e-6 for _, _, z in path.segments[0])
    assert path.segments[0][0][0] == 100.0 and path.end[0] == 199.5


def test_team_path_starts_once_the_team_has_landed_and_breaks_on_a_jump():
    a = Track(60.0, STEP, glide_then_walk(0, 0, 20, 100))
    b = Track(60.0, STEP, glide_then_walk(0, 10, 30, 90))
    path = team_path([a, b])
    assert 69 <= path.landed_s <= 76
    assert path.segments[0][0][0] >= path.landed_s
    # Last survivor 1 km away after the group is gone: a new piece, not a straight line.
    far = Track(115.0, STEP, [[10000, 10000]] * 20)
    assert len(team_path([a, b, far]).segments) == 2


def test_zone_close_time_is_when_the_next_zone_begins(match):  # noqa: F811
    # Shrinks at 200, 400 and 600 s: zone 1 has closed when zone 2 starts, and so on.
    assert zone_close_times(match) == [400.0, 600.0, 600.0]


def test_auto_draft_reads_points_off_the_replay_path(match, django_user_model):  # noqa: F811
    from apps.league.models import Team

    alpha = Team.objects.get(name="Alpha")
    # Alpha walks east 1 m per step from x=0 at t=100 s to t=700 s.
    PlayerTrack.objects.create(
        match=match,
        entity_id=1,
        team=alpha,
        start_s=100.0,
        step_s=STEP,
        points=[[i * 10, 0] for i in range(1201)],
    )
    call_command("redraft_rotations")
    points = {
        p.checkpoint: (round(p.x), round(p.z), p.game_time_s)
        for p in TeamRotation.objects.get(team=alpha).points.all()
    }
    assert points["DROP"] == (0, 0, 100.0)
    assert points["ZONE_1"] == (600, 0, 400.0)  # where it was when zone 1 had closed
    assert points["ZONE_2"][0] == 1000 and points["FINAL"][2] == 700.0
    # Bravo has no track: it keeps the drafts from kills and deaths.
    assert TeamRotation.objects.get(team__name="Bravo").points.first().evidence != {"replay": 1}

    staff = User.objects.create_user(email="s@tdl.test", password="x", is_staff=True)
    api = APIClient()
    api.force_authenticate(staff)
    rows = api.get(f"/api/v1/matches/{match.pk}/rotations").json()["rotations"]
    by_team = {r["team"]["name"]: r["path"] for r in rows}
    assert by_team["Bravo"] == []
    (segment,) = by_team["Alpha"]
    assert segment[0] == [100.0, 0.0, 0.0] and segment[-1] == [700.0, 1200.0, 0.0]
    assert len(segment) == 2  # a straight walk simplifies to its ends
