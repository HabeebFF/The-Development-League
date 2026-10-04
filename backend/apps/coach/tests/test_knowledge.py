import pytest
from rest_framework.test import APIClient

from apps.accounts.models import StaffProfile, User
from apps.league.models import Match, MatchDay, ScoringRule, Season, Stage
from apps.maps.models import Map, MapArea
from apps.results.models import MatchEvent

pytestmark = pytest.mark.django_db

SQUARE = [[0, 0], [100, 0], [100, 100], [0, 100]]


def client_for(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def analyst() -> APIClient:
    user = User.objects.create_user(email="analyst@tdl.test", password="pass-12345")
    StaffProfile.objects.create(user=user, role=StaffProfile.Role.ANALYST)
    return client_for(user)


@pytest.fixture
def player() -> APIClient:
    return client_for(User.objects.create_user(email="player@tdl.test", password="pass-12345"))


def test_starter_entries_are_there():
    from apps.coach.models import KnowledgeEntry

    titles = set(KnowledgeEntry.objects.values_list("title", flat=True))
    assert {"Gloo Wall", "UAV", "Bolt Maker", "Dinoculars"} <= titles
    assert KnowledgeEntry.objects.get(title="UAV").data["scan_radius_m"]["player_uav"] == 65


def test_staff_write_entries_and_players_cannot(analyst, player):
    body = {
        "kind": "MAP",
        "title": "Clock Tower drop",
        "body": "Tall building, contested.",
        "map": "bermuda",
    }
    assert player.post("/api/v1/coach/knowledge", body, format="json").status_code == 403

    made = analyst.post("/api/v1/coach/knowledge", body, format="json")
    assert made.status_code == 201, made.data
    assert made.data["map"] == "bermuda"
    assert made.data["updated_by"] == "analyst@tdl.test"

    # Researched drafts are loaded too; staff-written entries are approved straight away.
    listed = analyst.get("/api/v1/coach/knowledge?kind=MAP&map=bermuda&status=APPROVED").data
    assert [e["title"] for e in listed] == ["Clock Tower drop"]
    assert analyst.get("/api/v1/coach/knowledge?map=purgatory&status=APPROVED").data == []


def test_an_entry_about_an_area_takes_its_map(analyst):
    area = MapArea.objects.create(
        map=Map.objects.get(slug="kalahari"), name="Refinery", polygon=SQUARE
    )
    made = analyst.post(
        "/api/v1/coach/knowledge",
        {"kind": "MAP", "title": "Refinery", "area": area.pk},
        format="json",
    )
    assert made.status_code == 201, made.data
    assert made.data["map"] == "kalahari"
    assert made.data["area_name"] == "Refinery"

    wrong = analyst.post(
        "/api/v1/coach/knowledge",
        {"kind": "MAP", "title": "x", "area": area.pk, "map": "bermuda"},
        format="json",
    )
    assert wrong.status_code == 400


def test_staff_can_draw_map_areas(analyst, player):
    url = "/api/v1/admin/maps/solara/areas"
    assert player.post(url, {"name": "Port", "polygon": SQUARE}, format="json").status_code == 403
    made = analyst.post(url, {"name": "Port", "polygon": SQUARE}, format="json")
    assert made.status_code == 201, made.data
    assert made.data["centre_x"] == 50


def test_weapons_seen_in_matches_can_be_named(analyst):
    season = Season.objects.create(name="S1", scoring_rule=ScoringRule.objects.first())
    day = MatchDay.objects.create(stage=Stage.objects.create(season=season, name="L"), number=1)
    match = Match.objects.create(match_day=day, number=1, map=Map.objects.get(slug="bermuda"))
    for kind, weapon in [("KILL", 7), ("KILL", 7), ("KNOCK", 7), ("KILL", 9), ("DEATH", None)]:
        MatchEvent.objects.create(match=match, kind=kind, source="REPLAY_INFO", weapon_id=weapon)

    rows = analyst.get("/api/v1/coach/weapons").data
    assert [(r["weapon_id"], r["kills"], r["knocks"], r["name"]) for r in rows] == [
        (7, 2, 1, ""),
        (9, 1, 0, ""),
    ]

    named = analyst.put(
        "/api/v1/coach/weapons/7", {"name": "M1887", "weapon_class": "SHOTGUN"}, format="json"
    )
    assert named.status_code == 201, named.data
    assert (
        analyst.put(
            "/api/v1/coach/weapons/7", {"name": "M1887 (one shot)"}, format="json"
        ).status_code
        == 200
    )
    rows = analyst.get("/api/v1/coach/weapons").data
    assert rows[0]["name"] == "M1887 (one shot)"

    assert analyst.delete("/api/v1/coach/weapons/7").status_code == 204
    assert analyst.get("/api/v1/coach/weapons").data[0]["name"] == ""
