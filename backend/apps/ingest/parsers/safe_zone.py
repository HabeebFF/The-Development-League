"""``SafeZone_<matchId>_<timestamp>.log``: one line ``x,z``, e.g. ``-101,125``.

Several per match; callers order them by the filename timestamp
(``order_safe_zones``). Note: in the 2026-09-26 sample the value matched none of the
zone centres in the debugger log, so it is stored for reference only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from .base import FLOAT, ParseResult, split_lines
from .filenames import FileKind, classify

_POINT = re.compile(rf"^\s*{FLOAT}\s*,\s*{FLOAT}\s*$")


@dataclass(frozen=True)
class SafeZone:
    match_id: int | None
    timestamp: datetime | None
    x: float
    z: float


def parse(filename: str, content: str | bytes) -> ParseResult[SafeZone]:
    info = classify(filename)
    match_id = info.match_id if info.kind is FileKind.SAFE_ZONE else None
    lines = [line for line in split_lines(content) if line.strip()]
    result: ParseResult[SafeZone] = ParseResult(None)
    result.stats.lines = len(lines)
    if info.kind is not FileKind.SAFE_ZONE:
        result.warn("bad_filename", f"Not a SafeZone file name: {filename!r}")

    for i, line in enumerate(lines, start=1):
        m = _POINT.match(line)
        if m and result.data is None:
            result.data = SafeZone(match_id, info.timestamp, float(m[1]), float(m[2]))
            result.stats.parsed += 1
        else:
            result.stats.skipped += 1
            result.warn("unparsed_line", "Expected one 'x,z' line", i, line)

    if result.data is None and not lines:
        result.warn("empty", "SafeZone file is empty")
    return result


def order_safe_zones(zones: list[SafeZone]) -> list[SafeZone]:
    """Oldest first; zones without a timestamp go last, in their given order."""
    return sorted(zones, key=lambda z: (z.timestamp is None, z.timestamp or datetime.min))
