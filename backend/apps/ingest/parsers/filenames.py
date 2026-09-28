"""Classify an uploaded file by its name.

Observer files look like ``<Kind>_<matchId>_<YYYY-MM-DD-HH-MM-SS>.<ext>``, e.g.
``MatchResult_2103980121133858816_2026-09-27-00-05-01.log``. The session log is
``debugger-<timestamp>.log`` and has no match id (it covers many matches).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import PurePath

from .base import parse_filename_timestamp


class FileKind(StrEnum):
    MATCH_ID = "MATCH_ID"
    SAFE_ZONE = "SAFE_ZONE"
    MATCH_RESULT = "MATCH_RESULT"
    REPLAY_JSON = "REPLAY_JSON"
    REPLAY_BIN = "REPLAY_BIN"
    DEBUGGER = "DEBUGGER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FileInfo:
    kind: FileKind
    match_id: int | None = None
    timestamp: datetime | None = None
    raw_timestamp: str | None = None


_MATCH_FILE = re.compile(
    r"^(?P<prefix>MatchId|SafeZone|MatchResult|ReplayInfo)_(?P<match>\d+)_"
    r"(?P<ts>\d{4}(?:-\d{2}){5})\.(?P<ext>log|json|bin)$",
    re.IGNORECASE,
)
_DEBUGGER_FILE = re.compile(r"^debugger-(?P<ts>.+)\.log$", re.IGNORECASE)

_KINDS = {
    ("matchid", "log"): FileKind.MATCH_ID,
    ("safezone", "log"): FileKind.SAFE_ZONE,
    ("matchresult", "log"): FileKind.MATCH_RESULT,
    ("replayinfo", "json"): FileKind.REPLAY_JSON,
    ("replayinfo", "bin"): FileKind.REPLAY_BIN,
}


def classify(filename: str) -> FileInfo:
    """Return what kind of file this is, plus match id and timestamp when present.

    Accepts a bare name or a path (folder uploads send relative paths).
    """
    name = PurePath(filename.replace("\\", "/")).name.strip()

    m = _MATCH_FILE.match(name)
    if m:
        kind = _KINDS.get((m["prefix"].lower(), m["ext"].lower()), FileKind.UNKNOWN)
        if kind is FileKind.UNKNOWN:
            return FileInfo(FileKind.UNKNOWN)
        return FileInfo(
            kind=kind,
            match_id=int(m["match"]),
            timestamp=parse_filename_timestamp(m["ts"]),
            raw_timestamp=m["ts"],
        )

    m = _DEBUGGER_FILE.match(name)
    if m:
        raw = m["ts"]
        # Seen as 2026-09-26T19-41-10; tolerate the observer-file style too.
        ts = parse_filename_timestamp(raw.replace("T", "-"))
        return FileInfo(FileKind.DEBUGGER, timestamp=ts, raw_timestamp=raw)

    return FileInfo(FileKind.UNKNOWN)
