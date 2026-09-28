"""Clean Free Fire nicknames and team names.

In-game names are full of invisible filler characters (U+3164 HANGUL FILLER,
U+1160 HANGUL JUNGSEONG FILLER), odd-width spaces (U+2000, U+205F) and private-use
glyphs (U+F8FF). The same player's name can differ between files only by these
characters, so names are never used as keys (the game UID is). We keep:

- the raw name exactly as logged,
- a display name: invisible characters removed, odd spaces turned into a normal
  space, stylised letters (ᴰˢ, Ｋ) kept,
- a search name: the display name NFKC-normalised and case-folded.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Characters removed outright.
_INVISIBLE = {
    "ᅟ",  # HANGUL CHOSEONG FILLER
    "ᅠ",  # HANGUL JUNGSEONG FILLER
    "ㅤ",  # HANGUL FILLER
    "ﾠ",  # HALFWIDTH HANGUL FILLER
    "​",  # ZERO WIDTH SPACE
    "‌",  # ZERO WIDTH NON-JOINER
    "‍",  # ZERO WIDTH JOINER
    "⁠",  # WORD JOINER
    "﻿",  # BOM / ZERO WIDTH NO-BREAK SPACE
    "­",  # SOFT HYPHEN
}

# Characters turned into a plain space.
_SPACES = {" ", " ", "　", " ", *(chr(c) for c in range(0x2000, 0x200B))}

_MULTISPACE = re.compile(r" {2,}")


def _is_private_use(ch: str) -> bool:
    return unicodedata.category(ch) == "Co"


def display_name(raw: str) -> str:
    out = []
    for ch in raw:
        if ch in _INVISIBLE or _is_private_use(ch):
            # A filler usually stands where a space would be ("NBㅤVALSI").
            out.append(" " if ch in {"ㅤ", "ᅠ", "ﾠ", "ᅟ"} else "")
        elif ch in _SPACES or ch == "\t":
            out.append(" ")
        elif unicodedata.category(ch) == "Cc":
            continue
        else:
            out.append(ch)
    return _MULTISPACE.sub(" ", "".join(out)).strip()


def search_name(raw: str) -> str:
    return unicodedata.normalize("NFKC", display_name(raw)).casefold()


@dataclass(frozen=True)
class CleanName:
    raw: str
    display: str
    search: str


def clean(raw: str) -> CleanName:
    return CleanName(raw=raw, display=display_name(raw), search=search_name(raw))
