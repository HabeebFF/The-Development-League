"""Keeping 18+ and abusive words out of the names people choose (shown on leaderboards).

A name is squashed before checking: lower case, look-alike characters turned back into
letters (``f*ck``, ``sh1t``, ``p0rn``), and spaces, dots and repeated letters taken out, so
``F.U.C.K`` and ``fuuuck`` are caught too. Words that are often part of ordinary names
(``Sussex``, ``Therapist``) are only matched as whole words.

Staff can add words without a code change: ``BLOCKED_NAME_WORDS`` in the server's settings
(comma-separated) is matched like the whole-word list.
"""

from __future__ import annotations

import re
import unicodedata

from django.conf import settings

# Matched anywhere in the squashed name.
ANYWHERE = (
    "fuck", "fuk", "fck", "fvck", "shit", "cunt", "nigg", "niga", "fagot", "faggot",
    "whore", "slut", "bitch", "biatch", "pussy", "porn", "penis", "vagina", "dildo",
    "blowjob", "handjob", "horny", "masturbat", "orgasm", "ejaculat", "erection",
    "motherfuck", "asshole", "arsehole", "bastard", "retard", "paedo", "sexy",
    "hentai", "onlyfans", "xvideo", "pornhub", "ashawo", "olosho", "nudes",
)  # fmt: skip

# Matched only as a whole word (they turn up inside ordinary words and names).
WHOLE_WORD = (
    "ass", "arse", "cum", "sex", "pedo", "boobs", "cock", "dick", "tit", "tits", "rape", "anal",
    "nude", "naked", "xxx", "fag", "hoe", "thot", "milf", "prick", "toto", "kunt", "nsfw",
    "18plus", "rapist", "wank", "twat", "bollocks", "jizz", "spunk", "slag",
)  # fmt: skip

LOOKALIKES = str.maketrans(
    {"0": "o", "1": "i", "!": "i", "|": "i", "3": "e", "4": "a", "@": "a", "5": "s",
     "$": "s", "7": "t", "+": "t", "8": "b", "9": "g", "*": "u", "€": "e", "ß": "ss"}
)  # fmt: skip


def _plain(text: str) -> str:
    """Lower case without accents (é -> e) or look-alike characters."""
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.translate(LOOKALIKES)


def _squash(text: str) -> str:
    letters = re.sub(r"[^a-z]", "", text)
    return re.sub(r"(.)\1+", r"\1", letters)  # fuuuck -> fuck


def _extra() -> tuple[str, ...]:
    raw = getattr(settings, "BLOCKED_NAME_WORDS", "") or ""
    if isinstance(raw, (list, tuple)):
        raw = ",".join(raw)
    return tuple(w.strip().casefold() for w in raw.split(",") if w.strip())


def blocked_word(name: str) -> str | None:
    """The 18+ or abusive word in ``name``, or None when it's fine."""
    plain = _plain(name)
    letters = re.sub(r"[^a-z]", "", plain)
    squashed = _squash(plain)  # repeats taken out: fuuuck -> fuck
    for word in ANYWHERE:
        if word in letters or word in squashed:
            return word
    tokens = re.findall(r"[a-z0-9]+", plain)
    words = set(tokens) | {_squash(t) for t in tokens} | {letters, squashed}  # s.e.x -> sex
    for word in (*WHOLE_WORD, *_extra()):
        if word in words:
            return word
    return None


NAME_MESSAGE = "Pick another name: names can't include 18+ or offensive words."


def check_name(name: str) -> None:
    """Raise a DRF ValidationError when ``name`` has an 18+ or abusive word."""
    from rest_framework import serializers

    if name and blocked_word(name):
        raise serializers.ValidationError(NAME_MESSAGE)
