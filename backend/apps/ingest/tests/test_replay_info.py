import json

from apps.ingest.parsers import replay_info

NAME = "ReplayInfo_2103980121133858816_2026-09-26-23-48-55.json"


def test_real_file_meta(replay_json_bytes):
    result = replay_info.parse(NAME, replay_json_bytes)
    data = result.data
    assert result.warning_count == 0, result.warnings
    assert data.match_id == 2103980121133858816
    assert data.map_id == 3
    assert data.room_name == "TDL DAY 10"
    assert round(data.duration_s) == 966
    assert data.player_count == 52


def test_real_file_kills_and_eliminations(replay_json_bytes):
    data = replay_info.parse(NAME, replay_json_bytes).data
    assert len(data.kills) == 89
    first = data.kills[0]
    # RBL AMK (201326628) killed vM M4rSziN (218103833) at ~74 s.
    assert (first.killer_entity, first.victim_entity) == (201326628, 218103833)
    assert first.killer_name == "RBL AMK"

    assert len(data.eliminations) == 12  # 13 teams, the winner is never eliminated
    assert data.eliminations[0].team_name == "OUTPOST33 ESP"
    assert data.eliminations[-1].team_name == "BLUE LOCK G"


def test_real_file_uid_map_and_positions(replay_json_bytes):
    data = replay_info.parse(NAME, replay_json_bytes).data
    assert len(data.entity_to_uid) == 47
    assert data.entity_to_uid[167772182] == 2063288734  # NB VALSI
    assert data.actions and all(a.position is not None for a in data.actions)
    assert data.deaths and data.deaths[0].position is not None
    assert {e.event for e in data.other_events} == {2, 5}


def test_bad_json_never_raises():
    result = replay_info.parse(NAME, b"{not json")
    assert result.data is None
    assert result.warnings[0].code == "bad_json"
    assert replay_info.parse(NAME, "[]").warnings[0].code == "bad_json"


def test_partial_document():
    doc = {
        "MatchID": 1,
        "Events": [
            {"Event": 3, "PlayerID": 10, "Time": 5.0, "SParam": "victim"},
            {"Event": 1, "PlayerID": 10, "Time": 9.0, "SParam": "TEAM"},
            {"Event": 9},
            "junk",
        ],
    }
    result = replay_info.parse(NAME, json.dumps(doc))
    codes = [w.code for w in result.warnings]
    assert codes.count("bad_event") == 2
    assert "unpaired_kill" in codes
    assert "missing_field" in codes  # no PlayerHighlightInfos
    assert result.data.eliminations[0].team_name == "TEAM"
    assert result.data.kills == []
