from datetime import datetime

from apps.ingest.parsers import debugger
from apps.ingest.parsers.debugger import Point, player_index, team_slot

MATCH_ID = 2103980121133858816


def lines(*messages: str, start: str = "2026-09-26 20:04:24", frame: int = 237) -> list[str]:
    return [f"[{start}.{i:03d}][1][{frame + i}] {msg}" for i, msg in enumerate(messages)]


def one_block(*messages: str):
    result = debugger.parse_stream(
        lines(
            "SendEventLog: EventTypeEnterGame {}",
            *messages,
            f"SendLogEndGame  matchend matchid = {MATCH_ID} / user id = 1",
        )
    )
    assert len(result.data.blocks) == 1
    return result, result.data.blocks[0]


# -- The exact sample lines from the brief ----------------------------------------------


def test_spec_team_init_and_score():
    _, block = one_block(
        "OnTeamScoreInited -> TeamName: SOLAR FLARE TeamID: 3",
        "OnTeamScoreChanged -> TeamID: 8 TeamScore: 3",
    )
    assert block.teams == {3: "SOLAR FLARE"}
    assert block.team_scores == {8: 3}


def test_spec_kill():
    _, block = one_block("Player 134217781 Dead, killed by 201326620")
    kill = block.kills[0]
    assert (kill.victim, kill.killer) == (134217781, 201326620)
    assert kill.at == datetime(2026, 9, 26, 20, 4, 24, 1000)


def test_spec_knock_trace_sets_headshot():
    _, block = one_block(
        "Player '83886117' Knock Down, by '234881054'",
        "@zwj PlayKnockDownGunTrace killer=234881054 victim=83886117 headshot=True",
    )
    assert len(block.knocks) == 1
    assert block.knocks[0].headshot is True


def test_trace_without_knock_line_is_not_a_knock():
    _, block = one_block(
        "@zwj PlayKnockDownGunTrace killer=234881054 victim=83886117 headshot=False"
    )
    assert block.knocks == []


def test_spec_zone_line():
    _, block = one_block(
        "[InitByMessage] Update m_ZoneStatus : stageID = 0, OuterCenter = (-87.00, 0.00, -167.00), "
        "InnerCenter = (-188.54, 0.00, -41.12), InnerRadius = 550, TimeSpanType = ZONE_TYPE_SHRINK"
    )
    zone = block.zones[0]
    assert zone.stage == 0
    assert zone.state == "SHRINK"
    assert zone.outer == Point(-87.0, 0.0, -167.0)
    assert zone.inner == Point(-188.54, 0.0, -41.12)
    assert zone.inner_radius == 550


def test_repeated_zone_state_is_deduplicated():
    zone = (
        "[InitByMessage] Update m_ZoneStatus : stageID = 1, OuterCenter = (1.00, 0.00, 2.00), "
        "InnerCenter = (3.00, 0.00, 4.00), InnerRadius = 300, TimeSpanType = ZONE_TYPE_PRE_SHRINK, "
        "Received TimeSpanType = ZONE_TYPE_PRE_SHRINK"
    )
    _, block = one_block(zone, zone)
    assert len(block.zones) == 1


def test_spec_revive_and_teleport():
    _, block = one_block(
        "Revive Player 50331656, revivePosition=(74.06, 300.00, 428.30)",
        "**************SyncTeleportInfo, Position:(413.10, 22.13, 145.79) playerID:117440519 "
        "moveplatformID 0",
    )
    assert block.respawns[0].entity == 50331656
    assert block.respawns[0].position == Point(74.06, 300.0, 428.3)
    assert block.teleports[0].entity == 117440519
    assert block.teleports[0].position == Point(413.1, 22.13, 145.79)


def test_add_player_maps_entity_to_uid():
    add = "@ZX Match.AddPlayer userID : 503831916, service_group_id : 1677209530, playerID : "
    _, block = one_block(add + "33554434", add + "33554434")
    assert block.players == {33554434: 503831916}
    assert block.uid_of(33554434) == 503831916


def test_entity_helpers():
    assert team_slot(167772182) == 10
    assert player_index(167772182) == 22


# -- Splitting and robustness -----------------------------------------------------------


def test_map_id_after_end_line_and_block_bounds():
    result = debugger.parse_stream(
        lines(
            "lobby noise",
            "SendEventLog: EventTypeEnterGame {}",
            "Player 1 Dead, killed by 2",
            f"SendLogEndGame  matchend matchid = {MATCH_ID} / user id = 1",
            f'SendEventLog: EventTypeMicVoiceTime {{"match_id":{MATCH_ID},"map_id":3,"x":1}}',
        )
    )
    block = result.data.blocks[0]
    assert block.match_id == MATCH_ID
    assert block.map_id == 3
    assert (block.start_line, block.end_line) == (2, 4)
    assert result.data.lines_outside_blocks == 1


def test_two_matches_and_no_header_lines():
    text = (
        lines("SendEventLog: EventTypeEnterGame {}", "Player 1 Dead, killed by 2")
        + ["   at SomeStackTrace()"]
        + lines("SendLogEndGame  matchend matchid = 11 / user id = 1")
        + lines(
            "SendEventLog: EventTypeEnterGame {}",
            "Player 3 Dead, killed by 4",
            "SendLogEndGame  matchend matchid = 22 / user id = 1",
            start="2026-09-26 20:30:00",
        )
    )
    result = debugger.parse_stream(text)
    assert [b.match_id for b in result.data.blocks] == [11, 22]
    assert result.data.lines_without_header == 1
    assert result.warning_count == 0


def test_missing_end_line_falls_back():
    result = debugger.parse_stream(
        lines(
            "SendEventLog: EventTypeEnterGame {}",
            "Player 1 Dead, killed by 2",
            "SendEventLog: EventTypeEnterGame {}",
            "Player 3 Dead, killed by 4",
        )
    )
    blocks = result.data.blocks
    assert len(blocks) == 2
    assert all(b.match_id is None for b in blocks)
    assert [w.code for w in result.warnings] == ["block_without_end", "block_without_end"]


def test_zone_reset_starts_new_block():
    def zone(stage: int, state: str) -> str:
        return (
            f"[InitByMessage] Update m_ZoneStatus : stageID = {stage}, OuterCenter = (0.00, 0.00, "
            f"0.00), InnerCenter = (0.00, 0.00, 0.00), InnerRadius = 0, TimeSpanType = {state}"
        )

    result = debugger.parse_stream(
        lines(zone(0, "ZONE_TYPE_STABLE"), zone(1, "ZONE_TYPE_SHRINK"), zone(0, "ZONE_TYPE_STABLE"))
    )
    assert len(result.data.blocks) == 2
    assert all(b.implicit_start for b in result.data.blocks)


def test_team_init_after_kills_starts_new_block():
    result = debugger.parse_stream(
        lines(
            "OnTeamScoreInited -> TeamName: A TeamID: 1",
            "Player 1 Dead, killed by 2",
            "OnTeamScoreInited -> TeamName: B TeamID: 1",
        )
    )
    assert [b.teams for b in result.data.blocks] == [{1: "A"}, {1: "B"}]


def test_malformed_known_line_is_reported_not_raised():
    result, block = one_block("Player abc Dead, killed by xyz")
    assert block.kills == []
    assert result.warnings[0].code == "malformed_line"


def test_garbage_and_bytes_input():
    raw = [
        "﻿[2026-09-26 19:41:10.429][1][0] hello\r\n".encode(),
        b"\xff\xfe not utf8\n",
        b"[2026-99-99 99:99:99.000][1][0] bad time\n",
    ]
    result = debugger.parse_stream(raw)
    assert result.data.blocks == []
    assert {w.code for w in result.warnings} == {"bad_timestamp", "no_matches"}


def test_byte_offsets_point_at_block_start():
    raw = [
        (line + "\r\n").encode() for line in lines("noise", "SendEventLog: EventTypeEnterGame {}")
    ]
    raw += [(lines("SendLogEndGame  matchend matchid = 5 / user id = 1")[0] + "\r\n").encode()]
    block = debugger.parse_stream(raw).data.blocks[0]
    joined = b"".join(raw)
    assert joined[block.start_offset :].startswith(raw[1])
    assert joined[block.end_offset :].startswith(raw[2])


# -- Real excerpt of the sample session (match 2103980121133858816) ---------------------


def test_real_excerpt(debugger_excerpt_path):
    result = debugger.parse_file(str(debugger_excerpt_path))
    assert result.warning_count == 0, result.warnings
    session = result.data
    assert len(session.blocks) == 1
    block = session.block_for(MATCH_ID)
    assert block.map_id == 3
    assert block.summary() == {
        "match_id": MATCH_ID,
        "map_id": 3,
        "players": 52,
        "teams": 13,
        "kills": 89,
        "knocks": 124,
        "headshot_knocks": 16,
        "zone_updates": 11,
        "respawns": 41,
        "teleports": 1,
    }
    assert [z.inner_radius for z in block.zones if z.state == "PRE_SHRINK"] == [
        550,
        300,
        150,
        75,
        30,
    ]
