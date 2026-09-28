"""Checks that tie the three real sources for match 2103980121133858816 together.

These pin down the facts the rest of the pipeline relies on.
"""

from collections import Counter

import pytest

from apps.ingest.parsers import debugger, match_result, replay_info
from apps.ingest.parsers.debugger import team_slot

from .conftest import MATCH_RESULT_NAME, REPLAY_JSON_NAME


@pytest.fixture
def sources(match_result_bytes, replay_json_bytes, debugger_excerpt_path):
    result = match_result.parse(MATCH_RESULT_NAME, match_result_bytes).data
    replay = replay_info.parse(REPLAY_JSON_NAME, replay_json_bytes).data
    block = debugger.parse_file(str(debugger_excerpt_path)).data.blocks[0]
    return result, replay, block


def test_debugger_kills_per_uid_match_match_result(sources):
    result, _, block = sources
    kills = Counter(block.uid_of(k.killer) for k in block.kills)
    assert {p.uid: p.kills for p in result.players if p.kills} == dict(kills)


def test_replay_kills_match_debugger_kills(sources):
    _, replay, block = sources
    debugger_pairs = Counter((k.killer, k.victim) for k in block.kills)
    replay_pairs = Counter((k.killer_entity, k.victim_entity) for k in replay.kills)
    assert debugger_pairs == replay_pairs


def test_both_uid_maps_agree(sources):
    _, replay, block = sources
    for entity, uid in replay.entity_to_uid.items():
        assert block.players[entity] == uid


def test_slot_is_per_team_but_not_the_team_id(sources):
    result, _, block = sources
    team_id_by_name = {name: team_id for team_id, name in block.teams.items()}
    slots_by_team: dict[str, set[int]] = {}
    matches = 0
    for entity, uid in block.players.items():
        team = result.team_of(uid)
        slots_by_team.setdefault(team.name_raw, set()).add(team_slot(entity))
        matches += team_slot(entity) == team_id_by_name[team.name_raw]
    assert all(len(slots) == 1 for slots in slots_by_team.values())
    assert matches < len(block.players)  # so never use entity >> 24 as TeamID


def test_elimination_order_matches_ranks(sources):
    result, replay, _ = sources
    rank = {t.name_raw: t.rank for t in result.teams}
    ranks = [rank[e.team_name] for e in replay.eliminations]
    assert ranks == sorted(ranks, reverse=True)
