"""After-scrim review: the moments that cost a team, found from knocks, tracks and zones."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Membership, Plan, User
from apps.coach.engine import Game, Hit, TeamGame, Zone
from apps.coach.models import MatchReview
from apps.coach.moments import ALONE_M, LEAD_S, RULES, Player, downs, find, position
from apps.coach.tests.test_engine import walk
from apps.rotations.paths import Track

# Zone 1 at (0, 0) r=300 from 100 s, closes 300 s; Zone 2 at (0, 0) r=100 from 300 s, closes 500 s.
ZONES = [Zone(1, 0, 0, 300, 100, 300), Zone(2, 0, 0, 100, 300, 500)]
NAMES = {1: "Alpha", 2: "Bravo", 3: "Charlie"}


def line(*points: tuple[float, float, float], step: float = 0.5) -> Track:
    """A track through (t, x, z) points (metres), straight between them."""
    out = []
    t = points[0][0]
    while t <= points[-1][0]:
        for (t0, x0, z0), (t1, x1, z1) in zip(points, points[1:], strict=False):
            if t0 <= t <= t1:
                k = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                out.append([round((x0 + (x1 - x0) * k) * 10), round((z0 + (z1 - z0) * k) * 10)])
                break
        t += step
    return Track(points[0][0], step, out)


def still(x: float, z: float) -> Track:
    return line((0, x, z), (600, x, z))


def squad(team: int, *spots: tuple[float, float]) -> dict[int, Player]:
    return {
        team * 10 + i + 1: Player(team, f"P{team}{i + 1}", still(x, z))
        for i, (x, z) in enumerate(spots)
    }


def game(hits=(), eliminated=None, path=None) -> Game:
    teams = {
        1: TeamGame(1, 5, eliminated, path),
        2: TeamGame(2, 1, None, None),
        3: TeamGame(3, 2, None, None),
    }
    return Game(1, "M1", "bermuda", ZONES, list(hits), teams)


def kinds(review):
    return [(m["kind"], m["good"]) for m in review["moments"]]


def test_position_reads_the_nearest_sample_in_metres():
    tr = Track(10, 0.5, [[100, 200], None, None, [300, 400]])
    assert position(tr, 10) == (10, 20)
    assert position(tr, 11) == (30, 40)  # the hole is skipped
    assert position(tr, 100) is None
    assert position(None, 10) is None


def test_a_knock_then_the_kill_is_one_down():
    hits = [Hit(100, "KNOCK", 2, 1, 11), Hit(105, "KILL", 2, 1, 11), Hit(300, "KNOCK", 2, 1, 11)]
    assert [d.t for d in downs(hits)] == [100, 300]  # revived, then down again later


def test_caught_alone():
    players = squad(1, (200, 0), (0, 0), (5, 0), (0, 5))
    review = find(game([Hit(150, "KNOCK", 2, 1, 11)]), 1, players, NAMES)
    (m,) = review["moments"]
    assert m["kind"] == "alone" and m["players"] == ["P11"]
    assert "195 m from the nearest teammate" in m["detail"] and "Bravo" in m["detail"]
    assert m["clock"] == "2:30" and m["watch_s"] == 150 - LEAD_S


def test_a_knocked_teammate_nearby_does_not_count_as_cover():
    players = squad(1, (0, 0), (ALONE_M / 2, 0), (200, 0))
    hits = [Hit(140, "KNOCK", 2, 1, 11), Hit(150, "KNOCK", 2, 1, 12)]
    review = find(game(hits), 1, players, NAMES)
    second = [m for m in review["moments"] if "P12" in m["players"]]
    assert second and second[0]["kind"] == "alone"


def test_third_party_beats_the_other_checks():
    players = squad(1, (0, 0), (5, 0), (0, 5), (5, 5))
    hits = [Hit(140, "KNOCK", 1, 3, 31), Hit(150, "KNOCK", 2, 1, 12)]
    (m, *_) = [m for m in find(game(hits), 1, players, NAMES)["moments"] if not m["good"]]
    assert m["kind"] == "third_party"
    assert m["title"] == "Third-partied by Bravo" and "fighting Charlie" in m["detail"]


def test_untraded_and_traded_knocks():
    players = squad(1, (0, 0), (5, 0), (0, 5), (5, 5))
    lost = find(game([Hit(150, "KNOCK", 2, 1, 12)]), 1, players, NAMES)
    assert kinds(lost) == [("untraded", False)]
    hits = [Hit(150, "KNOCK", 2, 1, 12), Hit(155, "KNOCK", 1, 2, 21)]
    traded = find(game(hits), 1, players, NAMES)
    assert ("trade", True) in kinds(traded) and ("untraded", False) not in kinds(traded)


def test_caught_rotating_outside_the_zone():
    # The whole squad runs in from 400 m towards Zone 2 (r=100) together.
    players = {
        11 + i: Player(1, f"P1{i + 1}", line((0, 400 + i * 5, 0), (300, 400 + i * 5, 0),
                                               (400, 100 + i * 5, 0), (600, 0, 0)))
        for i in range(4)
    }  # fmt: skip
    review = find(game([Hit(350, "KNOCK", 2, 1, 11)]), 1, players, NAMES)
    assert kinds(review) == [("rotating", False)]
    assert review["moments"][0]["title"] == "Caught rotating into Zone 2"


def test_late_into_a_zone_from_the_team_path():
    path = walk((60, 200, 0), (520, 200, 0), (540, 50, 0), (600, 50, 0))
    review = find(game(path=path), 1, squad(1, (0, 0)), NAMES)
    (m,) = review["moments"]
    assert m["kind"] == "zone" and m["title"] == "Late into Zone 2" and m["t"] == 500
    assert "after Zone 2 closed" in m["detail"]


def test_downs_close_together_merge_and_a_wipe_is_called_out():
    players = squad(1, (200, 0), (0, 300), (0, 0), (5, 0))
    hits = [
        Hit(150, "KNOCK", 2, 1, 11),
        Hit(160, "KNOCK", 2, 1, 12),
        Hit(170, "KILL", 2, 1, 13),
        Hit(172, "KILL", 2, 1, 14),
    ]
    review = find(game(hits, eliminated=175), 1, players, NAMES)
    alone = [m for m in review["moments"] if m["kind"] == "alone"]
    assert len(alone) == 1 and alone[0]["players"] == ["P11", "P12"]
    assert alone[0]["title"] == "2 players caught alone"
    assert "wiped 25 s later" in alone[0]["detail"]
    assert review["wiped_by"] == "Bravo" and review["eliminated_clock"] == "2:55"


def test_at_most_three_bad_moments_and_one_good():
    players = squad(1, (0, 0), (5, 0), (500, 0), (0, 500))
    hits = [
        Hit(110, "KNOCK", 1, 3, 31),
        Hit(112, "KNOCK", 1, 3, 32),  # a fight won against Charlie
        Hit(150, "KNOCK", 2, 1, 13),  # alone
        Hit(200, "KNOCK", 3, 1, 14),  # alone
        Hit(260, "KNOCK", 2, 1, 11),  # not traded
        Hit(400, "KNOCK", 3, 1, 12),  # not traded
    ]
    review = find(game(hits), 1, players, NAMES)
    bad = [m for m in review["moments"] if not m["good"]]
    good = [m for m in review["moments"] if m["good"]]
    assert len(bad) == 3 and [m["kind"] for m in bad[:2]] == ["alone", "alone"]
    assert len(good) == 1 and good[0]["title"] == "Won the fight against Charlie"
    assert [m["t"] for m in review["moments"]] == sorted(m["t"] for m in review["moments"])


# -- API ---------------------------------------------------------------------------------------


@pytest.fixture
def published(db):
    from apps.league.models import Match, MatchDay, ScoringRule, Season, Stage, Team
    from apps.maps.models import Map
    from apps.results.models import MatchEvent, TeamMatchResult
    from apps.rotations.models import PlayerTrack

    plan = Plan.objects.get(code="league_team")
    alpha = Team.objects.create(name="Alpha", slug="alpha", plan=plan)
    bravo = Team.objects.create(name="Bravo", slug="bravo", plan=plan)
    season = Season.objects.create(name="S1", scoring_rule=ScoringRule.objects.first())
    stage = Stage.objects.create(season=season, name="L")
    day = MatchDay.objects.create(stage=stage, number=13, title="Day 13 8PM")
    match = Match.objects.create(
        match_day=day, number=1, map=Map.objects.get(slug="bermuda"),
        status=Match.Status.PUBLISHED,
    )  # fmt: skip
    for team, place in ((alpha, 2), (bravo, 1)):
        TeamMatchResult.objects.create(
            match=match, team=team, in_game_name=team.name, placement=place, kills=1,
            placement_points=0, kill_points=0, total_points=0,
        )  # fmt: skip
    for entity, team, x in ((11, alpha, 200), (12, alpha, 0), (21, bravo, 210)):
        PlayerTrack.objects.create(
            match=match, entity_id=entity, team=team, start_s=0, step_s=0.5,
            points=[[x * 10, 0]] * 1200,
        )  # fmt: skip
    MatchEvent.objects.create(
        match=match, kind=MatchEvent.Kind.KNOCK, source=MatchEvent.Source.DEBUGGER,
        game_time_s=150, actor_entity=21, target_entity=11, actor_team=bravo, target_team=alpha,
    )  # fmt: skip
    return match, alpha, bravo


def _member(team, email):
    user = User.objects.create_user(email=email)
    Membership.objects.create(user=user, team=team)
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_team_review_is_built_on_first_ask_and_private_to_the_team(published):
    match, alpha, bravo = published
    a = _member(alpha, "a@tdl.test")
    resp = a.get("/api/v1/coach/teams/alpha/review")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["day"]["label"] == "Day 13 8PM" and len(body["days"]) == 1
    (m,) = body["matches"]
    assert m["id"] == match.pk and m["map"] == "Bermuda" and m["placement"] == 2
    assert [x["kind"] for x in m["moments"]] == ["alone"]
    assert MatchReview.objects.filter(team=alpha).get().rules == RULES
    assert MatchReview.objects.count() == 2  # every team's review is made at once
    assert _member(bravo, "b@tdl.test").get("/api/v1/coach/teams/alpha/review").status_code == 403


def test_reviews_are_built_after_an_upload(published):
    from apps.coach.tasks import build_reviews_task

    match, alpha, _ = published
    assert build_reviews_task(match.pk) == 2
    assert MatchReview.objects.get(team=alpha).moments[0]["kind"] == "alone"
