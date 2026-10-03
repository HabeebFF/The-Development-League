"""Counter plans and when-to-rotate advice."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Membership, Plan, User
from apps.coach.counter import head_to_head, plays_from
from apps.coach.engine import Area, Game, Hit, TeamGame, Zone
from apps.coach.models import CounterPlan
from apps.coach.rotate import advice, left_drop
from apps.coach.tests.test_engine import SQUARE, walk
from apps.coach.tests.test_reports import fact
from apps.league.models import Team


def test_plays_come_from_the_opponents_facts_and_cite_them():
    facts = [
        fact("rotation.z3.late", "Got inside Zone 3 after it closed in 3 of 5", 0.6, 3, 5,
             [1, 2, 3], zone=3),
        fact("fights.z2", "During Zone 2: won 1, lost 4 of 5 fights", 0.2, 4, 6, [1, 2, 4, 5],
             zone=2, won=1, lost=4),
        fact("style.fights", "4.0 fights per match, first knock in 70%", 4.0, 6, 6, [1, 2]),
        fact("style.label", "Playstyle: aggressive", 4.0, 6, 6, [1, 2]),
        fact("bermuda:drops.usual", "Usual drop on Bermuda: Clock Tower", 0.8, 4, 5, [1, 2, 3, 4],
             "bermuda", place="Clock Tower", placement=6.0, x=0, z=0),
        # The same death spot overall and on one map: only the stronger one is kept.
        fact("deaths.top1", "9 player deaths at Mill, in 3 of 6", 9, 3, 6, [1, 2, 3], place="Mill"),
        fact("bermuda:deaths.top1", "9 player deaths at Mill on Bermuda, in 3 of 3", 9, 3, 3,
             [1, 2, 3], "bermuda", place="Mill"),
        fact("rotation.z1.early", "Rotated early into Zone 1 in 4 of 5", 0.8, 4, 5, [1, 2, 3, 4]),
        fact("rotation.z2.early", "Rotated early into Zone 2 in 3 of 5", 0.6, 3, 5, [1, 2, 3]),
        # Fewer than 40% late: not a pattern.
        fact("rotation.z2.late", "Late into Zone 2 in 1 of 5", 0.2, 1, 5, [2], zone=2),
    ]  # fmt: skip
    plays = plays_from(facts, "Cliq")
    titles = [p["title"] for p in plays]
    assert any(t.startswith("They reach Zone 3 late") for t in titles)
    assert any(t.startswith("They lose more fights than they win during Zone 2") for t in titles)
    assert any(t.startswith("They start most fights") for t in titles)
    assert any(t.startswith("Expect Cliq at Clock Tower on Bermuda") for t in titles)
    assert not any("Zone 2 late" in t for t in titles)
    assert [t for t in titles if "Mill" in t] == [
        "They often fall at Mill on Bermuda: a good place to set up against them"
    ]
    early = [p for p in plays if "early" in p["title"]]
    assert [p["title"] for p in early] == [
        "They rotate early into Zones 1 and 2: expect the centre to be taken, plan your own way in"
    ]
    assert early[0]["facts"] == ["rotation.z1.early", "rotation.z2.early"]
    for p in plays:
        assert p["facts"] and p["why"] and p["matches"]
    style = next(p for p in plays if "start most fights" in p["title"])
    assert style["facts"] == ["style.label", "style.fights"]


def _game(match, teams, hits=()):
    zones = [Zone(1, 0, 0, 300, 100, 300), Zone(2, 0, 0, 100, 300, 500)]
    return Game(match, f"M{match}", "bermuda", zones, list(hits), teams)


def test_head_to_head_counts_only_fights_between_the_two():
    teams = {i: TeamGame(i, i, None, None) for i in (1, 2, 3)}
    hits = [
        Hit(100, "KNOCK", 1, 2, 21),
        Hit(105, "KILL", 1, 2, 21),
        Hit(400, "KNOCK", 2, 1, 11),
        Hit(402, "KNOCK", 2, 1, 12),
        Hit(200, "KNOCK", 1, 3, 31),  # another team
    ]
    h2h = head_to_head([_game(7, teams, hits), _game(8, {1: teams[1], 3: teams[3]})], 1, 2)
    assert h2h == {"met": [7], "fights": 2, "won": 1, "lost": 1, "matches": [7]}


def test_rotation_advice_groups_drops_and_times_the_top_teams():
    def team(team_id, placement, leave_at, x=0):
        # Lands at (x, 0) at 60 s, waits, then runs 400 m into the zone.
        path = walk((60, x, 0), (leave_at, x, 0), (leave_at + 40, x + 400, 0), (900, x + 400, 0))
        return TeamGame(team_id, placement, None, path)

    games = []
    for match in (1, 2, 3):
        g = _game(
            match,
            {
                1: team(1, 2, 150 + match * 10),  # top 5 from the Refinery
                2: team(2, 9, 280, x=10),  # also the Refinery, finished low
                3: team(3, 4, 120, x=-900),  # an unnamed spot
            },
        )
        g.areas = [Area("Refinery", SQUARE)]
        games.append(g)
    out = advice(games, {1: "Alpha", 2: "Bravo", 3: "Cliq"})
    refinery = next(d for d in out["drops"] if d["place"] == "Refinery")
    assert refinery["matches"] == [1, 2, 3] and refinery["team_matches"] == 6
    assert refinery["top_finishes"] == 3
    # Alpha left at 160, 170, 180 s (+ the time to cover 250 m): median about 3:00.
    assert refinery["left_s"] == round(170 + 250 / 10)
    assert refinery["advice"][0].startswith("Teams that finished top 5 from here left by about 3:")
    assert [r["team"] for r in refinery["routes"]] == ["Alpha"] * 3
    assert all(r["path"] for r in refinery["routes"])
    assert len(out["zone_ends"]) == 3 and out["zone_ends"][0]["zone"] == 2


def test_left_drop_is_none_for_a_team_that_never_moved():
    path = walk((60, 0, 0), (500, 10, 0))
    assert left_drop(path, (60, 0, 0)) is None


# -- API ---------------------------------------------------------------------------------------


@pytest.fixture
def teams(db):
    plan = Plan.objects.get(code="league_team")
    return (Team.objects.create(name="Alpha", slug="alpha", plan=plan),
            Team.objects.create(name="Bravo", slug="bravo", plan=plan))  # fmt: skip


def _member(team, email):
    user = User.objects.create_user(email=email)
    Membership.objects.create(user=user, team=team)
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_counter_plan_is_for_the_asking_team_only_and_kept_for_the_week(teams):
    alpha, bravo = teams
    a, b = _member(alpha, "a@tdl.test"), _member(bravo, "b@tdl.test")
    resp = a.get("/api/v1/coach/teams/alpha/counter/bravo")
    assert resp.status_code == 200, resp.content
    assert resp.json()["opponent"] == "Bravo" and resp.json()["plays"] == []
    assert CounterPlan.objects.count() == 1
    a.get("/api/v1/coach/teams/alpha/counter/bravo")
    assert CounterPlan.objects.count() == 1  # nothing new played: the same plan
    assert b.get("/api/v1/coach/teams/alpha/counter/bravo").status_code == 403
    assert a.get("/api/v1/coach/teams/alpha/counter/alpha").status_code == 400
    assert APIClient().get("/api/v1/coach/teams/alpha/counter/bravo").status_code == 401


def test_rotation_advice_needs_the_coach(teams):
    alpha, _ = teams
    a = _member(alpha, "a@tdl.test")
    resp = a.get("/api/v1/coach/maps/bermuda/rotate")
    assert resp.status_code == 200 and resp.json()["drops"] == []
    assert a.get("/api/v1/coach/maps/nowhere/rotate").status_code == 404
    Team.objects.filter(pk=alpha.pk).update(plan=None)
    fresh = APIClient()
    fresh.force_authenticate(User.objects.get(email="a@tdl.test"))
    assert fresh.get("/api/v1/coach/maps/bermuda/rotate").status_code == 403
