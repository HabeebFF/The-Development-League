"""Researched knowledge arrives as drafts; staff stay in control."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import StaffProfile, User
from apps.coach import research
from apps.coach.models import KnowledgeEntry
from apps.coach.tests.test_knowledge import client_for
from apps.maps.models import Map, MapArea

pytestmark = pytest.mark.django_db

SOURCE = {"title": "OB55 patch notes", "url": "https://ff.garena.com/en/article/1712/",
          "publisher": "Garena", "published": "2026-09-10", "accessed": "2026-10-03"}  # fmt: skip


def _entry(title, body="Text.", kind="UTILITY", **extra):
    return {"kind": kind, "title": title, "map": None, "body": body, "data": {}, "patch": "OB55",
            "sources": [SOURCE], "conflicts": "", "weak": False, **extra}  # fmt: skip


def _load(*entries, areas=()):
    return research.load(
        {"entries": list(entries), "areas": list(areas)}, KnowledgeEntry, Map, MapArea
    )


def test_the_research_file_is_complete():
    payload = research.read()
    assert len(payload["entries"]) >= 100
    for item in payload["entries"]:
        assert item["body"].strip() and item["sources"], item["title"]
        assert all(s["url"].startswith("https://") for s in item["sources"]), item["title"]
        assert item["patch"], item["title"]
    for area in payload["areas"]:
        u0, v0, u1, v1 = area["box"]
        assert 0 <= u0 < u1 <= 1 and 0 <= v0 < v1 <= 1, area["name"]


def test_needs_writing_entries_are_filled_as_drafts_and_keep_our_numbers():
    KnowledgeEntry.objects.filter(title="UAV").update(body="", status="APPROVED", reviewed_at=None)
    counts = _load(
        _entry("UAV", "Shows enemies nearby.",
               data={"scan_radius_m": {"player_uav": 80, "general_uav": 100}, "duration_s": 8}),
    )  # fmt: skip
    assert counts["filled"] == 1
    uav = KnowledgeEntry.objects.get(title="UAV")
    assert uav.status == "DRAFT" and uav.origin == "RESEARCH" and uav.body
    assert uav.sources[0]["url"] == SOURCE["url"] and uav.patch == "OB55"
    # Our replay measurement wins; the disagreement is written down.
    assert uav.data["scan_radius_m"]["player_uav"] == 65 and uav.data["duration_s"] == 8
    assert "Our replay files measured scan_radius_m" in uav.conflicts
    assert not KnowledgeEntry.objects.for_coach().filter(title="UAV").exists()


def test_staff_work_is_never_overwritten_and_drafts_refresh():
    staff = KnowledgeEntry.objects.create(kind="UTILITY", title="Smoke", body="Ours.")
    rejected = KnowledgeEntry.objects.create(
        kind="UTILITY", title="Flash", body="Old.", status="REJECTED", origin="RESEARCH"
    )
    _load(_entry("Grenade", "First version."))
    counts = _load(_entry("Smoke", "Theirs."), _entry("Flash", "New."), _entry("Grenade", "v2."))
    assert counts == {"created": 0, "filled": 0, "refreshed": 1, "kept": 2, "areas": 0}
    staff.refresh_from_db()
    rejected.refresh_from_db()
    assert staff.body == "Ours." and rejected.body == "Old." and rejected.status == "REJECTED"
    assert KnowledgeEntry.objects.get(title="Grenade").body == "v2."


def test_place_outlines_are_suggested_on_calibrated_maps_only():
    Map.objects.filter(slug="bermuda").update(
        transform={"a": 1, "b": 0, "c": 0, "d": 0, "e": 1, "f": 0},
        image_width=1000,
        image_height=1000,
    )
    Map.objects.filter(slug="kalahari").update(transform=None)
    MapArea.objects.create(
        map=Map.objects.get(slug="bermuda"), name="Peak", polygon=[[0, 0], [9, 0], [9, 9]]
    )
    counts = _load(
        _entry("Bermuda: Clock Tower", kind="MAP", map="bermuda", place="Clock Tower"),
        _entry("Bermuda: Peak", kind="MAP", map="bermuda", place="Peak"),
        areas=[
            {"map": "bermuda", "name": "Clock Tower", "box": [0.5, 0.4, 0.6, 0.5], "note": "x"},
            {"map": "bermuda", "name": "Peak", "box": [0, 0, 0.1, 0.1]},
            {"map": "kalahari", "name": "Refinery", "box": [0, 0, 0.1, 0.1]},  # not calibrated
        ],
    )
    assert counts["areas"] == 1
    tower = MapArea.objects.get(name="Clock Tower")
    assert tower.status == "SUGGESTED" and tower.polygon[0] == [500.0, 400.0]
    assert (tower.centre_x, tower.centre_z) == pytest.approx((550, 450))
    entry = KnowledgeEntry.objects.get(title="Bermuda: Clock Tower")
    assert entry.area == tower and entry.map.slug == "bermuda"
    assert KnowledgeEntry.objects.get(title="Bermuda: Peak").area.status == "CONFIRMED"
    # Not used for labels until confirmed, and only staff see it.
    assert MapArea.find(tower.map_id, 550, 450) is None
    public = APIClient().get("/api/v1/maps/bermuda").json()
    assert [a["name"] for a in public["areas"]] == ["Peak"]
    user = User.objects.create_user(email="analyst@tdl.test", password="pass-12345")
    StaffProfile.objects.create(user=user, role=StaffProfile.Role.ANALYST)
    analyst = client_for(user)
    names = {a["name"]: a["status"] for a in analyst.get("/api/v1/maps/bermuda").json()["areas"]}
    assert names == {"Peak": "CONFIRMED", "Clock Tower": "SUGGESTED"}
    url = f"/api/v1/admin/maps/bermuda/areas/{tower.pk}"
    assert analyst.patch(url, {"status": "CONFIRMED"}, format="json").status_code == 200
    assert MapArea.find(tower.map_id, 550, 450) == tower


def test_staff_review_is_recorded():
    user = User.objects.create_user(email="analyst@tdl.test", password="pass-12345")
    StaffProfile.objects.create(user=user, role=StaffProfile.Role.ANALYST)
    analyst = client_for(user)
    _load(_entry("Grenade", "Throw it."))
    entry = KnowledgeEntry.objects.get(title="Grenade")
    drafts = analyst.get("/api/v1/coach/knowledge?status=DRAFT").json()
    assert entry.pk in [e["id"] for e in drafts]
    resp = analyst.patch(
        f"/api/v1/coach/knowledge/{entry.pk}", {"status": "APPROVED"}, format="json"
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["reviewed_by"] == "analyst@tdl.test"
    assert resp.json()["sources"][0]["published"] == "2026-09-10"
    assert KnowledgeEntry.objects.for_coach().filter(pk=entry.pk).exists()
