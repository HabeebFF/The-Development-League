"""End-to-end upload flow on the real files of match 2103980121133858816."""

from __future__ import annotations

from datetime import datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.ingest.models import ParseRun, UploadBatch, UploadedFile
from apps.league.models import Match, MatchDay, Player, ScoringRule, Season, Stage, Team, TeamAlias
from apps.maps.models import Map
from apps.results.models import MatchEvent, PlayerMatchResult, TeamMatchResult, ZonePhase

from .conftest import FIXTURES, MATCH_ID, MATCH_RESULT_NAME, REPLAY_JSON_NAME

pytestmark = pytest.mark.django_db

DEBUGGER_NAME = "debugger-2026-09-26T19-41-10.log"
SAFE_ZONE_NAME = f"SafeZone_{MATCH_ID}_2026-09-26-23-52-22.log"
MATCH_ID_NAME = f"MatchId_{MATCH_ID}_2026-09-26-23-48-55.log"
REPLAY_BIN_NAME = f"ReplayInfo_{MATCH_ID}_2026-09-26-23-48-55.bin"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def all_files() -> list[SimpleUploadedFile]:
    return [
        SimpleUploadedFile(MATCH_RESULT_NAME, fixture_bytes(MATCH_RESULT_NAME)),
        SimpleUploadedFile(REPLAY_JSON_NAME, fixture_bytes(REPLAY_JSON_NAME)),
        SimpleUploadedFile(
            DEBUGGER_NAME, fixture_bytes("debugger-excerpt-2103980121133858816.log")
        ),
        SimpleUploadedFile(SAFE_ZONE_NAME, "﻿-101,125\r\n".encode()),
        SimpleUploadedFile(MATCH_ID_NAME, "﻿".encode()),
        SimpleUploadedFile(REPLAY_BIN_NAME, b"\x00\x01binary"),
        SimpleUploadedFile("notes.txt", b"hello"),
    ]


@pytest.fixture
def staff(django_user_model):
    return django_user_model.objects.create_user(
        email="staff@tdl.test", password="x-long-password", is_staff=True
    )


@pytest.fixture
def client(staff) -> APIClient:
    api = APIClient()
    api.force_authenticate(staff)
    return api


@pytest.fixture
def match_day() -> MatchDay:
    season = Season.objects.create(
        name="Season 1",
        slug="season-1",
        scoring_rule=ScoringRule.objects.get(name="TDL default"),
        is_active=True,
    )
    stage = Stage.objects.create(season=season, name="League")
    return MatchDay.objects.create(stage=stage, number=10)


@pytest.fixture
def upload(client, django_capture_on_commit_callbacks):
    """Create a batch, upload files, run the (eager) grouping task; returns the batch JSON."""

    def run(files: list[SimpleUploadedFile]) -> dict:
        batch = client.post("/api/v1/uploads/batches", {"note": "day 10"}, format="json").json()
        with django_capture_on_commit_callbacks(execute=True):
            resp = client.post(
                f"/api/v1/uploads/batches/{batch['id']}/files", {"files": files}, format="multipart"
            )
        assert resp.status_code == 201, resp.content
        return client.get(f"/api/v1/uploads/batches/{batch['id']}").json()

    return run


@pytest.fixture
def confirm(client, django_capture_on_commit_callbacks):
    def run(batch_id: int, matches: list[dict]):
        with django_capture_on_commit_callbacks(execute=True):
            resp = client.post(
                f"/api/v1/uploads/batches/{batch_id}/confirm", {"matches": matches}, format="json"
            )
        return resp

    return run


def test_preview_groups_files_by_match(upload):
    batch = upload(all_files())
    assert batch["status"] == UploadBatch.Status.READY
    kinds = {f["original_name"]: (f["kind"], f["parse_status"]) for f in batch["files"]}
    assert kinds[MATCH_RESULT_NAME] == ("MATCH_RESULT", "OK")
    assert kinds[REPLAY_JSON_NAME] == ("REPLAY_JSON", "OK")
    assert kinds[DEBUGGER_NAME] == ("DEBUGGER", "OK")
    assert kinds[REPLAY_BIN_NAME] == ("REPLAY_BIN", "SKIPPED")
    assert kinds["notes.txt"] == ("UNKNOWN", "SKIPPED")

    preview = batch["preview"]
    assert len(preview["matches"]) == 1
    match = preview["matches"][0]
    assert match["game_match_id"] == str(MATCH_ID)  # a string: too big for JS numbers
    assert match["has_match_result"] and match["has_replay_info"] and match["has_debugger"]
    assert match["map"]["name"] == "Purgatory"
    assert match["room_name"] == "TDL DAY 10"
    assert match["match_day_hint"] == 10
    assert len(match["teams"]) == 13
    assert all(t["team"] is None for t in match["teams"])
    assert match["ready"] is True
    assert match["debugger_blocks"][0]["summary"]["kills"] == 89
    assert [(f["name"], f["kind"]) for f in preview["unassigned_files"]] == [
        ("notes.txt", "UNKNOWN")
    ]


def test_confirm_builds_the_match(upload, confirm, match_day):
    batch = upload(all_files())
    resp = confirm(
        batch["id"], [{"game_match_id": str(MATCH_ID), "match_day": match_day.pk, "number": 1}]
    )
    assert resp.status_code == 202, resp.content

    match = Match.objects.get(game_match_id=MATCH_ID)
    assert match.status == Match.Status.PUBLISHED
    assert match.map == Map.objects.get(name="Purgatory")
    assert match.room_name == "TDL DAY 10"
    assert match.safe_zones[0]["x"] == -101.0

    run = ParseRun.objects.get(match=match)
    assert run.status in {ParseRun.Status.OK, ParseRun.Status.WARNINGS}, run.error
    assert run.counts["teams"] == 13 and run.counts["players"] == 52

    noobz = TeamMatchResult.objects.get(match=match, in_game_name="NOOBZ ESPORTS")
    assert (noobz.placement, noobz.kills, noobz.total_points) == (1, 17, 29)
    assert noobz.slot == 10 and noobz.log_team_id == 2  # different numbers, both kept
    assert noobz.eliminated_at_s is None  # the winner
    outpost = TeamMatchResult.objects.get(match=match, in_game_name="OUTPOST33 ESP")
    assert outpost.placement_points == 0 and round(outpost.eliminated_at_s) == 153

    valsi = PlayerMatchResult.objects.get(match=match, player__game_uid=2063288734)
    assert valsi.display_name == "NB VALSIᴰˢ"
    assert valsi.kills == 9 and valsi.entity_id == 167772182
    assert valsi.knocks is not None
    assert sum(p.knocks for p in PlayerMatchResult.objects.filter(match=match)) == 124

    events = MatchEvent.objects.filter(match=match)
    assert events.filter(kind="KILL").count() == 89
    assert events.filter(kind="KNOCK").count() == 124
    assert events.filter(kind="TEAM_ELIMINATED").count() == 12
    assert events.filter(kind="RESPAWN").count() == 41
    kill = events.filter(kind="KILL").order_by("game_time_s").first()
    assert kill.actor_player.game_uid == 11559421022 and kill.x is not None  # RBL AMK
    assert abs(kill.game_time_s - 74.38) < 1.5  # aligned onto the replay's clock

    zones = ZonePhase.objects.filter(match=match, state="SHRINK").order_by("stage_index")
    assert [z.inner_radius for z in zones] == [550, 300, 150, 75, 30]
    assert [z.outer_radius for z in zones] == [None, 550, 300, 150, 75]

    batch_row = UploadBatch.objects.get(pk=batch["id"])
    assert batch_row.status == UploadBatch.Status.DONE
    assert batch_row.preview["results"][0]["status"] in {"OK", "WARNINGS"}
    assert TeamAlias.objects.filter(in_game_name="SAGE UNITED").exists()


def test_reupload_updates_and_never_duplicates(upload, confirm, match_day):
    first = upload(all_files())
    confirm(first["id"], [{"game_match_id": str(MATCH_ID), "match_day": match_day.pk, "number": 1}])
    teams_before = Team.objects.count()

    second = upload(all_files())
    statuses = {f["original_name"]: f["parse_status"] for f in second["files"]}
    assert statuses[MATCH_RESULT_NAME] == "DUPLICATE"
    assert second["preview"]["matches"][0]["existing_match"]["number"] == 1
    assert all(t["team"] is not None for t in second["preview"]["matches"][0]["teams"])

    resp = confirm(second["id"], [{"game_match_id": str(MATCH_ID)}])  # existing: no day needed
    assert resp.status_code == 202
    assert Match.objects.count() == 1
    assert Team.objects.count() == teams_before
    assert TeamMatchResult.objects.count() == 13
    assert PlayerMatchResult.objects.count() == 52
    assert MatchEvent.objects.filter(kind="KILL").count() == 89
    assert ParseRun.objects.count() == 2


def test_team_mapping_is_remembered(upload, confirm, match_day):
    noobz = Team.objects.create(name="Noobz", tag="NB")
    batch = upload(all_files())
    confirm(
        batch["id"],
        [
            {
                "game_match_id": str(MATCH_ID),
                "match_day": match_day.pk,
                "number": 1,
                "teams": {"NOOBZ ESPORTS": noobz.pk},
            }
        ],
    )
    assert TeamMatchResult.objects.get(placement=1).team == noobz
    assert TeamAlias.resolve("NOOBZ ESPORTS", None) == noobz
    assert Player.objects.get(game_uid=2063288734).current_team == noobz


def test_unknown_teams_fail_when_creation_is_off(upload, confirm, match_day):
    batch = upload(all_files())
    confirm(
        batch["id"],
        [
            {
                "game_match_id": str(MATCH_ID),
                "match_day": match_day.pk,
                "number": 1,
                "create_missing_teams": False,
            }
        ],
    )
    run = ParseRun.objects.get()
    assert run.status == ParseRun.Status.FAILED
    assert "Unknown in-game team names" in run.error
    assert UploadBatch.objects.get(pk=batch["id"]).status == UploadBatch.Status.FAILED
    assert Match.objects.get().status == Match.Status.NEEDS_REVIEW
    assert not TeamMatchResult.objects.exists()


def test_match_result_only(upload, confirm, match_day):
    batch = upload([SimpleUploadedFile(MATCH_RESULT_NAME, fixture_bytes(MATCH_RESULT_NAME))])
    preview = batch["preview"]["matches"][0]
    assert not preview["has_debugger"] and preview["map"] is None
    confirm(batch["id"], [{"game_match_id": str(MATCH_ID), "match_day": match_day.pk, "number": 2}])
    match = Match.objects.get()
    assert match.team_results.count() == 13
    assert PlayerMatchResult.objects.filter(knocks__isnull=True).count() == 52
    assert not match.events.exists()


def test_custom_scoring_rule(upload, confirm, match_day):
    rule = ScoringRule.objects.create(
        name="Double kills", placement_points={"1": 20}, points_per_kill=2
    )
    Season.objects.filter(pk=match_day.stage.season_id).update(scoring_rule=rule)
    batch = upload([SimpleUploadedFile(MATCH_RESULT_NAME, fixture_bytes(MATCH_RESULT_NAME))])
    confirm(batch["id"], [{"game_match_id": str(MATCH_ID), "match_day": match_day.pk, "number": 1}])
    noobz = TeamMatchResult.objects.get(placement=1)
    assert (noobz.placement_points, noobz.kill_points, noobz.total_points) == (20, 34, 54)
    assert TeamMatchResult.objects.get(placement=2).placement_points == 0


def test_debugger_block_without_end_is_linked_by_time(upload, confirm, match_day):
    text = fixture_bytes("debugger-excerpt-2103980121133858816.log")
    trimmed = b"".join(
        line for line in text.splitlines(keepends=True) if b"SendLogEndGame" not in line
    )
    batch = upload(
        [
            SimpleUploadedFile(MATCH_RESULT_NAME, fixture_bytes(MATCH_RESULT_NAME)),
            SimpleUploadedFile(DEBUGGER_NAME, trimmed),
        ]
    )
    preview = batch["preview"]["matches"][0]
    assert preview["has_debugger"]
    assert preview["debugger_blocks"][0]["summary"]["linked_by"] == "time"
    confirm(batch["id"], [{"game_match_id": str(MATCH_ID), "match_day": match_day.pk, "number": 1}])
    assert MatchEvent.objects.filter(kind="KNOCK").count() == 124


def test_confirm_validation(upload, confirm, match_day, client):
    batch = upload([SimpleUploadedFile(MATCH_RESULT_NAME, fixture_bytes(MATCH_RESULT_NAME))])
    assert confirm(batch["id"], [{"game_match_id": "123"}]).status_code == 400
    assert confirm(batch["id"], [{"game_match_id": str(MATCH_ID)}]).status_code == 400
    assert confirm(batch["id"], [{"game_match_id": "abc"}]).status_code == 400
    Match.objects.create(match_day=match_day, number=1)
    confirm(batch["id"], [{"game_match_id": str(MATCH_ID), "match_day": match_day.pk, "number": 1}])
    assert ParseRun.objects.count() == 0  # clash is caught before a match is created
    assert UploadBatch.objects.get(pk=batch["id"]).preview["results"][0]["status"] == "FAILED"


def test_permissions(client, staff, django_user_model):
    anon = APIClient()
    assert anon.get("/api/v1/uploads/batches").status_code == 401
    player = django_user_model.objects.create_user(email="p@tdl.test", password="x-long-password")
    other = APIClient()
    other.force_authenticate(player)
    assert other.post("/api/v1/uploads/batches", {}, format="json").status_code == 403
    assert client.get("/api/v1/uploads/batches").status_code == 200


def test_presign_needs_s3_and_register_checks_keys(client):
    batch = client.post("/api/v1/uploads/batches", {}, format="json").json()
    resp = client.post(
        f"/api/v1/uploads/batches/{batch['id']}/presign",
        {"files": [{"name": "a.log", "size": 1}]},
        format="json",
    )
    assert resp.status_code == 400
    resp = client.post(
        f"/api/v1/uploads/batches/{batch['id']}/register",
        {"files": [{"name": "a.log", "size": 1, "key": "uploads/999/x/a.log"}]},
        format="json",
    )
    assert resp.status_code == 400
    resp = client.post(
        f"/api/v1/uploads/batches/{batch['id']}/register",
        {"files": [{"name": "a.log", "size": 1, "key": f"uploads/{batch['id']}/x/a.log"}]},
        format="json",
    )
    assert resp.status_code == 400  # not in storage yet


def test_reprocess_and_parse_runs(
    upload, confirm, match_day, client, django_capture_on_commit_callbacks
):
    batch = upload(all_files())
    confirm(batch["id"], [{"game_match_id": str(MATCH_ID), "match_day": match_day.pk, "number": 1}])
    match = Match.objects.get()
    with django_capture_on_commit_callbacks(execute=True):
        assert client.post(f"/api/v1/matches/{match.pk}/reprocess").status_code == 202
    runs = client.get(f"/api/v1/matches/{match.pk}/parse-runs").json()
    assert runs["count"] == 2
    assert TeamMatchResult.objects.count() == 13


def test_broken_files_never_break_the_batch(upload):
    batch = upload(
        [
            SimpleUploadedFile(MATCH_RESULT_NAME, b"garbage"),
            SimpleUploadedFile(REPLAY_JSON_NAME, b"{not json"),
            SimpleUploadedFile(DEBUGGER_NAME, b"nothing useful\n"),
        ]
    )
    assert batch["status"] == "READY"
    assert {f["parse_status"] for f in batch["files"]} == {"FAILED"}
    assert batch["preview"]["matches"][0]["ready"] is False
    assert UploadedFile.objects.filter(parse_status="FAILED").count() == 3


def test_log_times_are_read_in_log_time_zone(settings, upload):
    settings.LOG_TIME_ZONE = "Africa/Lagos"
    batch = upload([SimpleUploadedFile(MATCH_RESULT_NAME, fixture_bytes(MATCH_RESULT_NAME))])
    stamp = batch["files"][0]["file_timestamp"]
    assert datetime.fromisoformat(stamp.replace("Z", "+00:00")).hour == 23  # 00:05 Lagos


def test_confirm_rebuilds_standings(upload, confirm, match_day):
    batch = upload(all_files())
    confirm(batch["id"], [{"game_match_id": str(MATCH_ID), "match_day": match_day.pk, "number": 1}])
    table = APIClient().get("/api/v1/seasons/season-1/standings").json()
    assert len(table["rows"]) == 13
    top = table["rows"][0]
    assert top["team"]["name"] == "NOOBZ ESPORTS"
    assert (top["rank"], top["total_points"], top["booyahs"], top["kills"]) == (1, 29, 1, 17)


def test_confirm_drafts_rotations(upload, confirm, match_day):
    from apps.rotations.models import RotationPoint, TeamRotation

    batch = upload(all_files())
    confirm(batch["id"], [{"game_match_id": str(MATCH_ID), "match_day": match_day.pk, "number": 1}])
    match = Match.objects.get(game_match_id=MATCH_ID)
    assert TeamRotation.objects.filter(match=match, status="AUTO").count() == 13
    noobz = TeamRotation.objects.get(match=match, team__name="NOOBZ ESPORTS")
    assert [p.checkpoint for p in noobz.points.all()][-1] == "FINAL"
    points = RotationPoint.objects.filter(rotation__match=match)
    assert points.filter(checkpoint="ELIMINATED").count() == 12
    assert points.filter(checkpoint="DROP").count() >= 10
