from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
MATCH_ID = 2103980121133858816
MATCH_RESULT_NAME = "MatchResult_2103980121133858816_2026-09-27-00-05-01.log"
REPLAY_JSON_NAME = "ReplayInfo_2103980121133858816_2026-09-26-23-48-55.json"
DEBUGGER_EXCERPT_NAME = "debugger-excerpt-2103980121133858816.log"


@pytest.fixture
def match_result_bytes() -> bytes:
    return (FIXTURES / MATCH_RESULT_NAME).read_bytes()


@pytest.fixture
def replay_json_bytes() -> bytes:
    return (FIXTURES / REPLAY_JSON_NAME).read_bytes()


@pytest.fixture
def debugger_excerpt_path() -> Path:
    return FIXTURES / DEBUGGER_EXCERPT_NAME
