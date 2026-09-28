"""Shared types and helpers for the log parsers.

Parsers never raise on bad file content. Anything they cannot understand becomes a
counted ``ParseWarning`` so the upload screen can show staff what was skipped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Generic, TypeVar

T = TypeVar("T")

# How many warnings are kept verbatim; the rest are only counted.
MAX_KEPT_WARNINGS = 50

BOM = "﻿"


@dataclass(frozen=True)
class ParseWarning:
    code: str
    message: str
    line_no: int | None = None
    line: str | None = None


@dataclass
class ParseStats:
    lines: int = 0
    parsed: int = 0
    skipped: int = 0


@dataclass
class ParseResult(Generic[T]):
    data: T | None
    warnings: list[ParseWarning] = field(default_factory=list)
    warning_count: int = 0
    stats: ParseStats = field(default_factory=ParseStats)

    @property
    def ok(self) -> bool:
        return self.data is not None

    def warn(
        self, code: str, message: str, line_no: int | None = None, line: str | None = None
    ) -> None:
        add_warning(self.warnings, code, message, line_no, line)
        self.warning_count += 1


def add_warning(
    warnings: list[ParseWarning],
    code: str,
    message: str,
    line_no: int | None = None,
    line: str | None = None,
) -> None:
    if len(warnings) < MAX_KEPT_WARNINGS:
        if line is not None and len(line) > 300:
            line = line[:300] + "..."
        warnings.append(ParseWarning(code, message, line_no, line))


def to_text(content: str | bytes) -> str:
    """Decode file content (UTF-8, optional BOM) and drop the BOM."""
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    return content.lstrip(BOM)


def split_lines(content: str | bytes) -> list[str]:
    """Split into lines, handling CRLF and a leading BOM."""
    return to_text(content).splitlines()


FILENAME_TS_FORMAT = "%Y-%m-%d-%H-%M-%S"

# A signed decimal number, captured.
FLOAT = r"(-?\d+(?:\.\d+)?)"


def parse_filename_timestamp(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, FILENAME_TS_FORMAT)
    except ValueError:
        return None
