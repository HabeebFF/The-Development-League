"""Teams, aliases, rosters and players API."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.league.models import Player, ScoringRule, Season, Team, TeamAlias

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_client() -> APIClient:
    client = APIClient()
    client.force_authenticate(User.objects.create_user(email="s@tdl.test", is_staff=True))
    return client


@pytest.fixture
def season() -> Season:
    return Season.objects.create(
        name="Season 1",
        slug="s1",
        is_active=True,
        scoring_rule=ScoringRule.objects.get(name="TDL default"),
    )


def test_public_team_list_and_detail(season):
    team = Team.objects.create(name="NOOBZ ESPORTS", tag="NB")
    Team.objects.create(name="Guest", is_league_member=False)
    anon = APIClient()
    names = [t["name"] for t in anon.get("/api/v1/teams").json()["results"]]
    assert names == ["NOOBZ ESPORTS"]
    assert anon.get("/api/v1/teams?search=nb").json()["count"] == 1
    detail = anon.get(f"/api/v1/teams/{team.slug}").json()
    assert detail["roster"] == []
    assert anon.post("/api/v1/teams", {"name": "x"}).status_code in (401, 403, 405)


def test_staff_create_team_with_validation(staff_client):
    bad = staff_client.post(
        "/api/v1/admin/teams",
        {"name": "Cliq", "primary_color": "red", "socials": {"myspace": "https://x"}},
        format="json",
    )
    assert bad.status_code == 400
    assert set(bad.json()) == {"primary_color", "socials"}
    resp = staff_client.post(
        "/api/v1/admin/teams",
        {
            "name": "Cliq",
            "tag": "CLQ",
            "primary_color": "#ff0055",
            "socials": {"instagram": "https://instagram.com/cliq"},
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["slug"] == "cliq" and resp.json()["primary_color"] == "#FF0055"
    assert APIClient().get("/api/v1/admin/teams").status_code == 401


def test_aliases(staff_client, season):
    team = Team.objects.create(name="Outpost 33")
    resp = staff_client.post(
        "/api/v1/admin/team-aliases",
        {"in_game_name": "OUTPOST33 ESP", "team": team.slug},
        format="json",
    )
    assert resp.status_code == 201
    dup = staff_client.post(
        "/api/v1/admin/team-aliases",
        {"in_game_name": "OUTPOST33 ESP", "team": team.slug},
        format="json",
    )
    assert dup.status_code == 400
    assert TeamAlias.resolve("OUTPOST33 ESP", season) == team


def test_rosters_and_player_admin(staff_client, season):
    team = Team.objects.create(name="NOOBZ ESPORTS")
    other = Team.objects.create(name="Cliq")
    Player.objects.create(
        game_uid=2063288734,
        current_name_raw="NB VALSI",
        display_name="NB VALSI",
        search_name="nb valsi",
    )
    resp = staff_client.post(
        "/api/v1/admin/rosters",
        {"player_uid": "2063288734", "team": team.slug, "season": "s1", "role": "IGL"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    clash = staff_client.post(
        "/api/v1/admin/rosters",
        {"player_uid": "2063288734", "team": other.slug, "season": "s1"},
        format="json",
    )
    assert clash.status_code == 400
    unknown = staff_client.post(
        "/api/v1/admin/rosters",
        {"player_uid": "999", "team": team.slug, "season": "s1"},
        format="json",
    )
    assert unknown.status_code == 400

    roster = APIClient().get(f"/api/v1/teams/{team.slug}").json()["roster"]
    assert roster[0]["player"]["game_uid"] == "2063288734" and roster[0]["role"] == "IGL"

    found = staff_client.get("/api/v1/admin/players?search=2063288734").json()["results"]
    assert found[0]["display_name"] == "NB VALSI"
    assert staff_client.get("/api/v1/admin/players?search=valsi").json()["count"] == 1
    pk = found[0]["id"]
    patched = staff_client.patch(
        f"/api/v1/admin/players/{pk}",
        {"display_name": "VALSI", "current_team": team.slug},
        format="json",
    )
    assert patched.status_code == 200 and patched.json()["current_team"] == team.slug
