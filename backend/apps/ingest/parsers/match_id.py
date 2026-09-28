"""``MatchId_<matchId>_<YYYY-MM-DD-HH-MM-SS>.log``.

The file body is empty (at most a BOM); all information is in the filename.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .base import ParseResult, to_text
from .filenames import FileKind, classify


@dataclass(frozen=True)
class MatchIdFile:
    match_id: int
    started_at: datetime | None


def parse(filename: str, content: str | bytes = b"") -> ParseResult[MatchIdFile]:
    info = classify(filename)
    if info.kind is not FileKind.MATCH_ID or info.match_id is None:
        result: ParseResult[MatchIdFile] = ParseResult(None)
        result.warn("bad_filename", f"Not a MatchId file name: {filename!r}")
        return result

    result = ParseResult(MatchIdFile(info.match_id, info.timestamp))
    if info.timestamp is None:
        result.warn("bad_timestamp", f"Could not read the time in {filename!r}")
    if to_text(content).strip():
        result.warn("unexpected_content", "MatchId file is normally empty; body ignored")
    return result
