"""New teams signing themselves up: create, checks, staff review, roster (NEW-TEAMS.md)."""

from __future__ import annotations

import io
import json

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import Membership, Plan, StaffProfile
from apps.league.models import (
    Match,
    MatchDay,
    Player,
    RosterEntry,
    ScoringRule,
    Season,
    Stage,
    Team,
    TeamAlias,
)
from apps.results.models import PlayerMatchResult

pytestmark = pytest.mark.django_db
URL = "/api/v1/me/new-team"


def make_user(email, **kw):
    return get_user_model().objects.create_user(email=email, password="pw-123456", **kw)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def season():
    rule = ScoringRule.objects.create(name="TDL", placement_points={"1": 12})
    return Season.objects.create(name="Season 1", scoring_rule=rule, is_active=True)


@pytest.fixture
def staff():
    user = make_user("staff@tdl.test")
    StaffProfile.objects.create(user=user)
    return user


@pytest.fixture
def boss():
    return make_user("boss@kings.test", display_name="Kings Boss")


def roster(*uids, igl=None):
    roles = ["RUSHER", "SNIPER", "GRENADER", "ALL_ROUNDER"] * 2
    return [
        {"uid": str(u), "name": f"NBK P{i}", "role": roles[i], "igl": u == igl}
        for i, u in enumerate(uids)
    ]


def form(**over):
    data = {
        "name": "Nairobi Kings",
        "tag": "NBK",
        "country": "KE",
        "contact": "+254 700 000000",
        "lobby_name": "NBK ESPORTS",
        "roster": roster(1000001, 1000002, 1000003, 1000004, igl=1000001),
    }
    data.update(over)
    return data


def create(user, **over):
    return client_for(user).post(URL, form(**over), format="json")


# -- creating ---------------------------------------------------------------------------------


def test_create_team_makes_creator_manager_and_waits(boss):
    resp = create(boss)
    assert resp.status_code == 201, resp.content
    team = Team.objects.get(name="Nairobi Kings")
    assert team.status == Team.Status.PENDING
    assert not team.is_league_member and team.plan is None
    assert team.tag == "NBK" and team.country == "KE" and team.created_by == boss
    assert [r["uid"] for r in team.pending_roster] == ["1000001", "1000002", "1000003", "1000004"]
    assert boss.manages(team)
    # Nothing on the league yet: no players made, not on public pages.
    assert not Player.objects.exists()
    assert APIClient().get("/api/v1/teams").json()["count"] == 0
    mine = client_for(boss).get(URL).json()
    assert mine["team"]["status"] == "PENDING" and mine["can_create"] is False
    me = client_for(boss).get("/api/v1/me").json()
    assert me["memberships"][0]["team"]["status"] == "PENDING"


def test_create_with_logo_multipart(boss):
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "gold").save(buf, "PNG")
    logo = SimpleUploadedFile("logo.png", buf.getvalue(), content_type="image/png")
    data = form()
    data["roster"] = json.dumps(data["roster"])
    resp = client_for(boss).post(URL, {**data, "logo": logo}, format="multipart")
    assert resp.status_code == 201, resp.content
    assert Team.objects.get(name="Nairobi Kings").logo


def test_bad_logo_refused(boss):
    logo = SimpleUploadedFile("logo.png", b"not a picture", content_type="image/png")
    data = form()
    data["roster"] = json.dumps(data["roster"])
    resp = client_for(boss).post(URL, {**data, "logo": logo}, format="multipart")
    assert resp.status_code == 400 and "logo" in resp.json()
    assert not Team.objects.exists()


def test_roster_size_4_to_6(boss):
    resp = create(boss, roster=roster(1, 2, 3))
    assert resp.status_code == 400 and "4 to 6" in resp.json()["roster"]
    resp = create(boss, roster=roster(*range(100001, 100008)))
    assert resp.status_code == 400
    assert create(boss, roster=roster(*range(100001, 100007))).status_code == 201


def test_name_tag_and_lobby_clashes_blocked(boss):
    Team.objects.create(name="SLF", tag="SLF")
    other = Team.objects.create(name="NOOBZ")
    TeamAlias.objects.create(team=other, in_game_name="NOOBZ ESPORTS")
    resp = create(boss, name="slf", tag="slf", lobby_name="noobz esports").json()
    assert "SLF already uses this name" in resp["name"]
    assert "SLF already uses this tag" in resp["tag"]
    assert "NOOBZ" in resp["lobby_name"]


def test_bad_rows_marked(boss):
    rows = roster(1000001, 1000002, 1000003, 1000004)
    rows[1]["uid"] = "12ab"
    rows[2]["uid"] = "1000001"
    rows[3]["role"] = ""
    resp = create(boss, roster=rows)
    assert resp.status_code == 400
    errors = [p["error"] for p in resp.json()["players"]]
    assert errors[0] is None
    assert "digits" in errors[1] and "twice" in errors[2] and "role" in errors[3]


def test_uid_on_another_waiting_team_blocked(boss):
    create(boss)
    other = make_user("other@tdl.test")
    resp = create(
        other, name="Accra Lions", tag="ACL", lobby_name="", roster=roster(1000001, 5, 6, 7)
    )
    assert resp.status_code == 400
    rows = resp.json()["players"]
    assert "Nairobi Kings" in rows[0]["error"]


def test_uid_that_played_elsewhere_is_flagged_not_blocked(boss, season):
    slf = Team.objects.create(name="SLF", tag="SLF")
    zaza = Player.objects.create(
        game_uid=1000002, current_name_raw="SLF ZAZA", display_name="SLF ZAZA", search_name="zaza"
    )
    stage = Stage.objects.create(season=season, name="Scrims")
    day = MatchDay.objects.create(stage=stage, number=1)
    match = Match.objects.create(match_day=day, number=1)
    PlayerMatchResult.objects.create(
        match=match, player=zaza, team=slf, raw_name="SLF ZAZA", display_name="SLF ZAZA"
    )
    check = client_for(boss).post(f"{URL}/check", form(), format="json").json()
    assert check["errors"] == {} and check["roster"] is None
    row = check["players"][1]
    assert row["error"] is None and "last played for SLF" in row["flag"]
    assert row["known"]["name"] == "SLF ZAZA"
    assert create(boss).status_code == 201


def test_one_team_at_a_time_and_not_if_on_a_team(boss):
    assert create(boss).status_code == 201
    again = create(boss, name="Kings 2", tag="NBK2", lobby_name="")
    assert again.status_code == 400 and "already on" in again.json()["detail"]
    player = make_user("p@tdl.test")
    Membership.objects.create(user=player, team=Team.objects.create(name="SLF"))
    assert create(player, name="X Team", tag="XT", lobby_name="").status_code == 400


def test_staff_cant_create(staff):
    assert create(staff).status_code == 400


def test_edit_and_withdraw(boss):
    create(boss)
    changed = client_for(boss).patch(URL, form(tag="KINGS"), format="json")
    assert changed.status_code == 200, changed.content
    assert Team.objects.get().tag == "KINGS"
    assert client_for(boss).delete(URL).status_code == 204
    assert not Team.objects.exists() and not Membership.objects.exists()


# -- staff review ---------------------------------------------------------------------------------


def test_staff_list_and_approve(boss, staff, season):
    Plan.objects.get_or_create(code=Plan.LEAGUE_TEAM, defaults={"name": "League team"})
    old = Player.objects.create(
        game_uid=1000003, current_name_raw="OLD", display_name="OLD NAME", search_name="old"
    )
    slf = Team.objects.create(name="SLF")
    RosterEntry.objects.create(player=old, team=slf, season=season)
    create(boss)
    listed = client_for(staff).get("/api/v1/admin/new-teams").json()
    assert [t["name"] for t in listed["waiting"]] == ["Nairobi Kings"]
    assert listed["waiting"][0]["manager"]["email"] == "boss@kings.test"
    assert "SLF's roster" in listed["waiting"][0]["players"][2]["flag"]

    resp = client_for(staff).post("/api/v1/admin/new-teams/nairobi-kings/approve")
    assert resp.status_code == 200, resp.content
    team = Team.objects.get(name="Nairobi Kings")
    assert team.status == Team.Status.APPROVED and team.is_league_member
    assert team.plan.code == Plan.LEAGUE_TEAM and team.pending_roster == []
    assert TeamAlias.resolve("NBK ESPORTS", None) == team
    # New UIDs become players under the typed name; the known one keeps its log name.
    assert Player.objects.get(game_uid=1000001).display_name == "NBK P0"
    old.refresh_from_db()
    assert old.display_name == "OLD NAME" and old.current_team == team
    assert team.igl.game_uid == 1000001
    active = RosterEntry.objects.filter(team=team, left_on__isnull=True)
    assert active.count() == 4
    # The moved player left SLF's roster.
    assert RosterEntry.objects.get(team=slf).left_on is not None
    assert APIClient().get("/api/v1/teams").json()["count"] == 2


def test_reject_needs_reason_and_manager_can_resubmit(boss, staff):
    create(boss)
    url = "/api/v1/admin/new-teams/nairobi-kings/reject"
    assert client_for(staff).post(url, {}, format="json").status_code == 400
    resp = client_for(staff).post(url, {"reason": "Send your roster screenshot"}, format="json")
    assert resp.status_code == 200
    mine = client_for(boss).get(URL).json()["team"]
    assert mine["status"] == "REJECTED" and mine["review_note"] == "Send your roster screenshot"
    # The rejected team keeps its name while the manager fixes it.
    assert create(make_user("x@tdl.test"), lobby_name="").json()["name"]
    client_for(boss).patch(URL, form(), format="json")
    assert Team.objects.get().status == Team.Status.PENDING


def test_only_staff_review(boss):
    create(boss)
    resp = client_for(boss).post("/api/v1/admin/new-teams/nairobi-kings/approve")
    assert resp.status_code == 403


# -- squad of an approved team -------------------------------------------------------------------


@pytest.fixture
def kings(boss, staff, season):
    create(boss)
    client_for(staff).post("/api/v1/admin/new-teams/nairobi-kings/approve")
    return Team.objects.get(name="Nairobi Kings")


def test_squad_add_remove(boss, kings):
    url = "/api/v1/teams/nairobi-kings/squad"
    got = client_for(boss).get(url).json()
    assert len(got["players"]) == 4 and got["max"] == 6
    added = client_for(boss).post(
        url, {"uid": "2000001", "name": "NBK NEW", "role": "SNIPER"}, format="json"
    )
    assert added.status_code == 200, added.content
    assert len(added.json()["players"]) == 5
    again = client_for(boss).post(
        url, {"uid": "2000001", "name": "NBK NEW", "role": "SNIPER"}, format="json"
    )
    assert "already on your roster" in again.json()["detail"]
    pid = Player.objects.get(game_uid=2000001).pk
    removed = client_for(boss).delete(f"{url}?player={pid}")
    assert removed.status_code == 200 and len(removed.json()["players"]) == 4


def test_squad_max_six(boss, kings):
    url = "/api/v1/teams/nairobi-kings/squad"
    for uid in (2000001, 2000002):
        client_for(boss).post(url, {"uid": str(uid), "name": "N", "role": "RUSHER"}, format="json")
    resp = client_for(boss).post(url, {"uid": "2000003", "name": "N", "role": "RUSHER"})
    assert resp.status_code == 400 and "at most 6" in resp.json()["detail"]


def test_squad_cant_take_another_teams_player_but_staff_can(boss, staff, kings, season):
    slf = Team.objects.create(name="SLF")
    star = Player.objects.create(
        game_uid=3000001, current_name_raw="SLF STAR", display_name="SLF STAR", search_name="s"
    )
    RosterEntry.objects.create(player=star, team=slf, season=season)
    url = "/api/v1/teams/nairobi-kings/squad"
    row = {"uid": "3000001", "name": "STAR", "role": "RUSHER"}
    resp = client_for(boss).post(url, row, format="json")
    assert resp.status_code == 400 and "SLF's roster" in resp.json()["detail"]
    assert client_for(staff).post(url, row, format="json").status_code == 200
    assert RosterEntry.objects.get(team=slf).left_on is not None


def test_squad_only_for_managers(kings):
    outsider = make_user("out@tdl.test")
    url = "/api/v1/teams/nairobi-kings/squad"
    assert client_for(outsider).get(url).status_code == 403
    row = {"uid": "2000001", "name": "N", "role": "RUSHER"}
    assert client_for(outsider).post(url, row, format="json").status_code == 403
