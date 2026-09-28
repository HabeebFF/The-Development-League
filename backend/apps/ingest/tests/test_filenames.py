from datetime import datetime

import pytest

from apps.ingest.parsers.filenames import FileKind, classify


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("MatchId_2103980121133858816_2026-09-26-23-48-55.log", FileKind.MATCH_ID),
        ("SafeZone_2103980121133858816_2026-09-26-23-52-22.log", FileKind.SAFE_ZONE),
        ("MatchResult_2103980121133858816_2026-09-27-00-05-01.log", FileKind.MATCH_RESULT),
        ("ReplayInfo_2103980121133858816_2026-09-26-23-48-55.json", FileKind.REPLAY_JSON),
        ("ReplayInfo_2103980121133858816_2026-09-26-23-48-55.bin", FileKind.REPLAY_BIN),
    ],
)
def test_match_files(name, kind):
    info = classify(name)
    assert info.kind is kind
    assert info.match_id == 2103980121133858816
    assert info.timestamp is not None


def test_timestamp_and_folder_path():
    info = classify("logs\\day10/MatchId_2103980121133858816_2026-09-26-23-48-55.log")
    assert info.kind is FileKind.MATCH_ID
    assert info.timestamp == datetime(2026, 9, 26, 23, 48, 55)


def test_debugger_file():
    info = classify("debugger-2026-09-26T19-41-10.log")
    assert info.kind is FileKind.DEBUGGER
    assert info.match_id is None
    assert info.timestamp == datetime(2026, 9, 26, 19, 41, 10)


@pytest.mark.parametrize(
    "name",
    [
        "notes.txt",
        "MatchResult_abc_2026-09-26-23-48-55.log",
        "MatchResult_2103980121133858816_2026-09-26-23-48-55.json",
        "ReplayInfo_2103980121133858816_2026-09-26-23-48-55.log",
        "",
    ],
)
def test_unknown(name):
    assert classify(name).kind is FileKind.UNKNOWN
