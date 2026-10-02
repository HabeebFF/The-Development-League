"""Seasons, stages, groups, match days, matches, fixtures and standings API."""

import datetime as dt

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.testing import signed_in_client
from apps.league.models import Group, Match, MatchDay, Player, ScoringRule, Season, Stage, Team
from apps.results.models import PlayerMatchResult, StandingRow, TeamMatchResult

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_client() -> APIClient:
    client = APIClient()
    client.force_authenticate(User.objects.create_user(email="s@tdl.test", is_staff=True))
    return client


@pytest.fixture
def admin_client() -> APIClient:
    client = APIClient()
    client.force_authenticate(
        User.objects.create_user(email="boss@tdl.test", is_staff=True, is_superuser=True)
    )
    return client


@pytest.fixture
def commit(django_capture_on_commit_callbacks):
    """Run on-commit callbacks (the standings rebuild) as the real request would."""
    return lambda: django_capture_on_commit_callbacks(execute=True)


@pytest.fixture
def league(staff_client, commit):
    """A season built through the API: one group stage, two groups, one played match."""
    with commit():
        s = staff_client.post("/api/v1/admin/seasons", {"name": "Season One"}, format="json")
    assert s.status_code == 201, s.content
    assert s.json()["slug"] == "season-one" and s.json()["tiebreakers"][0] == "total_points"
    a, b, c, d = (Team.objects.create(name=n) for n in ["Alpha", "Bravo", "Charlie", "Delta"])
    stage = staff_client.post(
        "/api/v1/admin/stages", {"season": "season-one", "name": "Groups"}, format="json"
    ).json()
    with commit():
        ga = staff_client.post(
            "/api/v1/admin/groups",
            {"stage": stage["id"], "name": "A", "teams": ["alpha", "bravo"]},
            format="json",
        ).json()
        gb = staff_client.post(
            "/api/v1/admin/groups",
            {"stage": stage["id"], "name": "B", "teams": ["charlie", "delta"]},
            format="json",
        ).json()
    day = staff_client.post(
        "/api/v1/admin/match-days",
        {"stage": stage["id"], "group": ga["id"], "number": 1, "date": "2026-10-01"},
        format="json",
    ).json()
    m1 = staff_client.post(
        "/api/v1/admin/matches",
        {
            "match_day": day["id"],
            "number": 1,
            "map": "bermuda",
            "scheduled_at": "2026-10-01T18:00Z",
        },
        format="json",
    ).json()
    m2 = staff_client.post(
        "/api/v1/admin/matches", {"match_day": day["id"], "number": 2}, format="json"
    ).json()
    # Results arrive through the upload flow; here they are written directly.
    match = Match.objects.get(pk=m1["id"])
    for team, placement, kills in [(a, 1, 4), (b, 2, 1)]:
        TeamMatchResult.objects.create(
            match=match,
            team=team,
            in_game_name=team.name,
            placement=placement,
            kills=kills,
            placement_points=0,
            kill_points=0,
            total_points=0,
        )
    player = Player.objects.create(
        game_uid=2063288734,
        current_name_raw="NB VALSI",
        display_name="NB VALSI",
        search_name="nb valsi",
    )
    PlayerMatchResult.objects.create(
        match=match,
        player=player,
        team=a,
        raw_name="NB VALSI",
        display_name="NB VALSI",
        kills=4,
        is_mvp=True,
    )
    match.game_match_id = 2103980121133858816
    match.save()
    with commit():
        resp = staff_client.patch(
            f"/api/v1/admin/matches/{m1['id']}", {"status": "PUBLISHED"}, format="json"
        )
    assert resp.status_code == 200, resp.content
    return {
        "stage": stage,
        "ga": ga,
        "gb": gb,
        "day": day,
        "m1": m1,
        "m2": m2,
        "teams": (a, b, c, d),
    }


def test_public_seasons(league):
    viewer = signed_in_client()
    seasons = viewer.get("/api/v1/seasons").json()
    assert [s["slug"] for s in seasons["results"]] == ["season-one"]
    detail = viewer.get("/api/v1/seasons/season-one").json()
    assert detail["scoring"]["placement_points"]["1"] == 12
    groups = detail["stages"][0]["groups"]
    assert [(g["name"], [t["slug"] for t in g["teams"]]) for g in groups] == [
        ("A", ["alpha", "bravo"]),
        ("B", ["charlie", "delta"]),
    ]


def test_public_standings_scopes(league):
    viewer = signed_in_client()
    base = "/api/v1/seasons/season-one/standings"
    season = viewer.get(base).json()
    assert season["scope"] == "season"
    assert [(r["rank"], r["team"]["slug"], r["total_points"]) for r in season["rows"]] == [
        (1, "alpha", 16),
        (2, "bravo", 10),
    ]
    assert season["rows"][0]["form"] == [1] and season["rows"][0]["booyahs"] == 1

    group_b = viewer.get(f"{base}?group={league['gb']['id']}").json()
    assert [r["total_points"] for r in group_b["rows"]] == [0, 0]
    assert viewer.get(f"{base}?match_day={league['day']['id']}").json()["rows"][0]["kills"] == 4
    assert viewer.get(f"{base}?stage={league['stage']['id']}").json()["scope"].startswith("stage:")

    other = Season.objects.create(name="Other", scoring_rule=ScoringRule.objects.first())
    foreign = Group.objects.create(stage=Stage.objects.create(season=other, name="X"), name="Z")
    assert viewer.get(f"{base}?group={foreign.pk}").status_code == 404
    assert viewer.get(f"{base}?group=abc").status_code == 400


def test_public_fixtures_and_match_days(league):
    viewer = signed_in_client()
    fixtures = viewer.get("/api/v1/seasons/season-one/fixtures").json()
    assert fixtures["count"] == 1
    day = fixtures["results"][0]
    assert (day["stage"], day["group"], day["date"]) == ("Groups", "A", "2026-10-01")
    played, upcoming = day["matches"]
    assert played["played"] and played["booyah"]["slug"] == "alpha" and played["map"] == "bermuda"
    assert not upcoming["played"] and upcoming["booyah"] is None
    assert viewer.get("/api/v1/seasons/season-one/fixtures?upcoming=true").json()["count"] == 1

    Match.objects.filter(pk=league["m2"]["id"]).delete()
    assert viewer.get("/api/v1/seasons/season-one/fixtures?upcoming=true").json()["count"] == 0

    detail = viewer.get(f"/api/v1/match-days/{league['day']['id']}").json()
    assert detail["season"] == "season-one"
    assert [r["team"]["slug"] for r in detail["standings"]] == ["alpha", "bravo"]
    assert viewer.get("/api/v1/match-days?season=season-one").json()["count"] == 1


def test_public_matches_hide_unpublished(league):
    viewer = signed_in_client()
    listed = viewer.get("/api/v1/matches?season=season-one").json()
    assert [m["id"] for m in listed["results"]] == [league["m1"]["id"]]
    assert viewer.get("/api/v1/matches?team=charlie").json()["count"] == 0
    assert viewer.get("/api/v1/matches?team=alpha&map=bermuda").json()["count"] == 1
    assert viewer.get(f"/api/v1/matches/{league['m2']['id']}").status_code == 404

    detail = viewer.get(f"/api/v1/matches/{league['m1']['id']}").json()
    assert detail["game_match_id"] == "2103980121133858816"
    first = detail["results"][0]
    assert (first["placement"], first["team"]["slug"], first["total_points"]) == (1, "alpha", 16)
    assert first["players"][0]["game_uid"] == "2063288734" and first["players"][0]["is_mvp"]
    assert detail["results"][1]["players"] == []


def test_unpublishing_and_deleting_update_standings(league, staff_client, commit):
    m1 = league["m1"]["id"]
    with commit():
        staff_client.patch(f"/api/v1/admin/matches/{m1}", {"status": "NEEDS_REVIEW"}, format="json")
    rows = signed_in_client().get("/api/v1/seasons/season-one/standings").json()["rows"]
    assert rows == []

    with commit():
        staff_client.patch(f"/api/v1/admin/matches/{m1}", {"status": "PUBLISHED"}, format="json")
    assert StandingRow.objects.filter(scope="season").count() == 2
    with commit():
        assert staff_client.delete(f"/api/v1/admin/matches/{m1}").status_code == 204
    assert StandingRow.objects.filter(scope="season").count() == 0


def test_moving_a_match_day_to_another_season_rebuilds_both(league, staff_client, commit):
    other = staff_client.post("/api/v1/admin/seasons", {"name": "Season Two"}, format="json")
    stage2 = staff_client.post(
        "/api/v1/admin/stages", {"season": other.json()["slug"], "name": "League"}, format="json"
    ).json()
    with commit():
        resp = staff_client.patch(
            f"/api/v1/admin/match-days/{league['day']['id']}",
            {"stage": stage2["id"], "group": None},
            format="json",
        )
    assert resp.status_code == 200, resp.content
    viewer = signed_in_client()
    assert viewer.get("/api/v1/seasons/season-one/standings").json()["rows"] == []
    assert len(viewer.get("/api/v1/seasons/season-two/standings").json()["rows"]) == 2


def test_scoring_rule_changes_rescore(league, admin_client, staff_client, commit):
    rule = ScoringRule.objects.get(name="TDL default")
    assert (
        staff_client.patch(
            f"/api/v1/admin/scoring-rules/{rule.pk}", {"points_per_kill": 2}, format="json"
        ).status_code
        == 403
    )
    bad = admin_client.patch(
        f"/api/v1/admin/scoring-rules/{rule.pk}", {"placement_points": {"one": 12}}, format="json"
    )
    assert bad.status_code == 400
    with commit():
        ok = admin_client.patch(
            f"/api/v1/admin/scoring-rules/{rule.pk}", {"points_per_kill": 2}, format="json"
        )
    assert ok.status_code == 200, ok.content
    rows = signed_in_client().get("/api/v1/seasons/season-one/standings").json()["rows"]
    assert [r["total_points"] for r in rows] == [20, 11]
    assert admin_client.delete(f"/api/v1/admin/scoring-rules/{rule.pk}").status_code == 400


def test_tiebreaker_edit_and_manual_rebuild(league, staff_client, commit):
    bad = staff_client.patch(
        "/api/v1/admin/seasons/season-one", {"tiebreakers": ["kills", "vibes"]}, format="json"
    )
    assert bad.status_code == 400
    dupe = staff_client.patch(
        "/api/v1/admin/seasons/season-one", {"tiebreakers": ["kills", "kills"]}, format="json"
    )
    assert dupe.status_code == 400
    StandingRow.objects.all().delete()
    with commit():
        resp = staff_client.post("/api/v1/admin/seasons/season-one/rebuild-standings")
    assert resp.status_code == 202
    assert StandingRow.objects.filter(scope="season").count() == 2


def test_structure_validation(league, staff_client):
    stage, ga = league["stage"], league["ga"]
    other_stage = staff_client.post(
        "/api/v1/admin/stages",
        {"season": "season-one", "name": "Finals", "kind": "FINAL"},
        format="json",
    ).json()
    assert (
        staff_client.post(
            "/api/v1/admin/stages", {"season": "season-one", "name": "Groups"}, format="json"
        ).status_code
        == 400
    )
    # A group from another stage
    resp = staff_client.post(
        "/api/v1/admin/match-days",
        {"stage": other_stage["id"], "group": ga["id"], "number": 1},
        format="json",
    )
    assert resp.status_code == 400 and "group" in resp.json()
    # Match day numbers are unique per stage and group
    resp = staff_client.post(
        "/api/v1/admin/match-days",
        {"stage": stage["id"], "group": ga["id"], "number": 1},
        format="json",
    )
    assert resp.status_code == 400 and "number" in resp.json()
    # A team can only be in one group per stage
    resp = staff_client.post(
        "/api/v1/admin/groups",
        {"stage": stage["id"], "name": "C", "teams": ["alpha"]},
        format="json",
    )
    assert resp.status_code == 400 and "teams" in resp.json()
    # Match numbers are unique per day; publishing needs results; PROCESSING is not settable
    day = league["day"]["id"]
    resp = staff_client.post(
        "/api/v1/admin/matches", {"match_day": day, "number": 1}, format="json"
    )
    assert resp.status_code == 400 and "number" in resp.json()
    m2 = league["m2"]["id"]
    for status in ("PUBLISHED", "PROCESSING"):
        resp = staff_client.patch(f"/api/v1/admin/matches/{m2}", {"status": status}, format="json")
        assert resp.status_code == 400
    # Dates
    resp = staff_client.patch(
        "/api/v1/admin/seasons/season-one",
        {"starts_on": "2026-10-10", "ends_on": "2026-10-01"},
        format="json",
    )
    assert resp.status_code == 400
    # Things with matches can't be deleted
    assert staff_client.delete(f"/api/v1/admin/stages/{stage['id']}").status_code == 400
    assert staff_client.delete(f"/api/v1/admin/match-days/{day}").status_code == 400
    assert staff_client.delete("/api/v1/admin/seasons/season-one").status_code == 400
    assert staff_client.delete(f"/api/v1/admin/stages/{other_stage['id']}").status_code == 204


def test_one_active_season(staff_client):
    staff_client.post("/api/v1/admin/seasons", {"name": "S1", "is_active": True}, format="json")
    staff_client.post("/api/v1/admin/seasons", {"name": "S2", "is_active": True}, format="json")
    assert list(Season.objects.filter(is_active=True).values_list("slug", flat=True)) == ["s2"]


def test_league_data_needs_sign_in(league):
    # The whole site is login-only (Habeeb, 2026-10-02): no league data without an account.
    anon = APIClient()
    for url in [
        "/api/v1/seasons",
        "/api/v1/seasons/season-one/standings",
        "/api/v1/seasons/season-one/fixtures",
        "/api/v1/match-days",
        "/api/v1/matches",
        "/api/v1/teams",
        "/api/v1/maps",
    ]:
        assert anon.get(url).status_code == 401, url
        assert signed_in_client().get(url).status_code == 200, url


def test_staff_only(league):
    anon, player = APIClient(), APIClient()
    player.force_authenticate(User.objects.create_user(email="p@tdl.test"))
    for url in ["/api/v1/admin/seasons", "/api/v1/admin/matches", "/api/v1/admin/groups"]:
        assert anon.get(url).status_code == 401
        assert player.get(url).status_code == 403
    assert player.post("/api/v1/seasons", {"name": "x"}).status_code == 405
    assert anon.get("/api/v1/admin/scoring-rules").status_code == 401


def test_match_day_dates_order_fixtures(league, staff_client):
    stage = league["stage"]["id"]
    staff_client.post(
        "/api/v1/admin/match-days",
        {"stage": stage, "group": league["gb"]["id"], "number": 1, "date": "2026-09-30"},
        format="json",
    )
    days = signed_in_client().get("/api/v1/seasons/season-one/fixtures").json()["results"]
    assert [d["date"] for d in days] == ["2026-09-30", "2026-10-01"]
    assert MatchDay.objects.get(date=dt.date(2026, 9, 30)).group.name == "B"
