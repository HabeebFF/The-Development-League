"""The AI writer: turns template report tasks and counter-plan plays into plain coaching
advice, and checks every word of it against our facts before anyone sees it.

The AI never reads match data. It gets the items the template already chose (each with
the facts behind it), those facts' text, and the approved knowledge entries that mention
the same things. For each item it returns a title, one or two sentences of advice and the
ids it relied on. The server then checks each item:

- it cites at least one of the item's own facts, and nothing it wasn't given;
- every number in its text appears in what it cited (a fact's text or numbers, or a
  knowledge entry), so it can't make up a percentage, a time or a count;
- it is short.

An item that fails keeps its template text. If the writer is off, has no key, is over its
daily, per-minute or monthly limit, or the call fails, everything stays as the template
wrote it. Every call is recorded in ``AiUsage``.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from collections.abc import Iterable, Sequence
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT_S = 30
MAX_TITLE = 120
MAX_ADVICE = 320
MAX_KNOWLEDGE = 8
KNOWLEDGE_CHARS = 500
# USD per million tokens (input, output) when the Google key has billing turned on. Only
# used when a monthly cap is set; with no cap the key is treated as free tier.
PRICES = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
}

SYSTEM = (
    "You are the coach of a Free Fire esports squad. You are given coaching items that a"
    " program chose from the team's own match data, the facts behind them, and some"
    " general knowledge. Rewrite each item for players: a short title (at most 14 words)"
    " and advice of one or two sentences (at most 45 words) saying what to do differently."
    " Use only the facts and knowledge given. Every number you write must appear in a fact"
    " or knowledge entry you cite. Do not mention places, weapons, characters, teams or"
    " numbers that are not in what you cite. In 'cites', list the fact ids (and knowledge"
    " ids starting with k:) you used; always include at least one of the item's own facts."
    " Return one output item per input item, with the same n."
)

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "n": {"type": "INTEGER"},
                    "title": {"type": "STRING"},
                    "advice": {"type": "STRING"},
                    "cites": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["n", "title", "advice", "cites"],
            },
        }
    },
    "required": ["items"],
}


class WriterError(Exception):
    pass


# -- Limits -------------------------------------------------------------------------------


def label() -> str:
    """What reports record as their writer (fits beside counter.RULES in 40 characters)."""
    return f"gemini:{settings.GEMINI_MODEL}"[:29]


def unavailable(*, wait: bool = False) -> str | None:
    """Why the writer can't run now, or None when it can."""
    from .models import AiUsage

    if settings.COACH_WRITER != "gemini":
        return "The AI writer is off."
    if not settings.GEMINI_API_KEY:
        return "No Gemini key is set on the server."
    now = timezone.now()
    today = AiUsage.objects.filter(created_at__date=timezone.localdate())
    if today.count() >= settings.COACH_AI_DAILY_REQUESTS:
        return f"Today's limit of {settings.COACH_AI_DAILY_REQUESTS} requests is used up."
    cap = settings.COACH_AI_MONTHLY_CAP_USD
    if cap > 0 and month_cost() >= Decimal(str(cap)):
        return f"This month's ${cap:g} cap is reached."
    recent = AiUsage.objects.filter(created_at__gte=now - timedelta(seconds=60))
    if recent.count() >= settings.COACH_AI_PER_MINUTE:
        if not wait:
            return "Too many requests this minute."
        oldest = recent.order_by("created_at").first().created_at
        time.sleep(max(0.0, 60.5 - (now - oldest).total_seconds()))
    return None


def month_cost() -> Decimal:
    from .models import AiUsage

    start = timezone.localdate().replace(day=1)
    total = AiUsage.objects.filter(created_at__date__gte=start).aggregate(s=Sum("cost_usd"))
    return total["s"] or Decimal(0)


def cost(model: str, tokens_in: int, tokens_out: int) -> Decimal:
    if settings.COACH_AI_MONTHLY_CAP_USD <= 0:
        return Decimal(0)  # free tier
    p_in, p_out = PRICES.get(model, max(PRICES.values()))
    return Decimal(str(round((tokens_in * p_in + tokens_out * p_out) / 1e6, 6)))


# -- Checking -----------------------------------------------------------------------------

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _norm(n: str) -> str:
    n = n.replace(",", ".")
    return n.rstrip("0").rstrip(".") if "." in n else n


def numbers_in(text: str) -> set[str]:
    return {_norm(n) for n in _NUMBER.findall(text)}


def _walk(value) -> Iterable[str]:
    if isinstance(value, bool):
        return
    if isinstance(value, int | float):
        yield _norm(f"{value:g}")
        yield _norm(f"{round(value, 1):g}")
        yield str(round(value))
        if 0 < abs(value) <= 1:  # a share: 0.4 is written as 40%
            yield str(round(value * 100))
    elif isinstance(value, str):
        yield from numbers_in(value)
    elif isinstance(value, dict):
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, list | tuple):
        for v in value:
            yield from _walk(v)


def source_numbers(source: dict) -> set[str]:
    """Every number a fact or knowledge entry states."""
    keys = ("text", "title", "body", "value", "n", "of", "data")
    return {n for k in keys if k in source for n in _walk(source[k])}


def check(item: dict, answer: dict, sources: dict[str, dict]) -> str | None:
    """Why ``answer`` can't replace ``item``, or None when it passes."""
    title = str(answer.get("title", "")).strip()
    advice = str(answer.get("advice", "")).strip()
    cites = [str(c) for c in answer.get("cites", []) if str(c).strip()]
    if not title or not advice:
        return "empty"
    if len(title) > MAX_TITLE or len(advice) > MAX_ADVICE:
        return "too long"
    unknown = [c for c in cites if c not in sources]
    if unknown:
        return f"cites unknown {unknown[0]}"
    if not set(cites) & set(item["facts"]):
        return "cites none of the item's facts"
    allowed = set().union(*(source_numbers(sources[c]) for c in cites))
    missing = numbers_in(f"{title} {advice}") - allowed
    if missing:
        return f"number {sorted(missing)[0]} not in what it cites"
    return None


# -- Knowledge ----------------------------------------------------------------------------


def knowledge_for(facts: Sequence[dict]) -> list[dict]:
    """Approved entries that are about something these facts mention."""
    from .models import KnowledgeEntry

    text = " ".join(
        [f["text"] for f in facts] + [str(v) for f in facts for v in f.get("data", {}).values()]
    ).lower()
    maps = {f.get("map") for f in facts if f.get("map")}
    rotation = any(f["topic"] == "rotation" for f in facts)
    picked = []
    for e in KnowledgeEntry.objects.for_coach().select_related("map"):
        name = e.title.split(": ", 1)[-1].lower()
        about_place = e.map is None or e.map.slug in maps
        if (about_place and len(name) > 3 and name in text) or (rotation and e.kind == "ZONE"):
            picked.append(
                {
                    "id": f"k:{e.pk}",
                    "title": e.title,
                    "body": e.body[:KNOWLEDGE_CHARS],
                    "data": e.data,
                }  # fmt: skip
            )
    return picked[:MAX_KNOWLEDGE]


# -- Calling the model --------------------------------------------------------------------


def _gemini(prompt: str) -> tuple[dict, int, int]:
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
        },
    }
    req = urllib.request.Request(
        GEMINI_URL.format(model=settings.GEMINI_MODEL),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": settings.GEMINI_API_KEY},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            out = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise WriterError(f"Gemini answered {e.code}") from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise WriterError(f"Gemini call failed: {type(e).__name__}") from e
    usage = out.get("usageMetadata", {})
    try:
        text = out["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
    except (KeyError, IndexError, ValueError) as e:
        raise WriterError("Gemini returned no usable answer") from e
    return parsed, usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0)


def rewrite(
    feature: str,
    items: list[dict],
    facts: Sequence[dict],
    *,
    team: str,
    opponent: str | None = None,
    wait: bool = False,
) -> tuple[list[dict], int]:
    """``items`` with checked AI titles and advice where they pass. Returns the items and
    how many were rewritten (0 means the template text stands)."""
    from .models import AiUsage

    if not items or unavailable(wait=wait):
        return items, 0
    by_id = {f["id"]: f for f in facts}
    knowledge = knowledge_for([by_id[i] for it in items for i in it["facts"] if i in by_id])
    sources = {**by_id, **{k["id"]: k for k in knowledge}}
    prompt = json.dumps(
        {
            "team": team,
            "opponent": opponent,
            "items": [
                {"n": n, "title": it["title"], "facts": it["facts"]}
                for n, it in enumerate(items, 1)
            ],
            "facts": [
                {"id": f["id"], "text": f["text"], "map": f.get("map")}
                for f in facts
                if any(f["id"] in it["facts"] for it in items)
            ],
            "knowledge": knowledge,
        }
    )
    record = AiUsage(feature=feature, provider="gemini", model=settings.GEMINI_MODEL,
                     items=len(items))  # fmt: skip
    try:
        parsed, tokens_in, tokens_out = _gemini(prompt)
    except WriterError as e:
        logger.warning("Coach writer: %s", e)
        record.ok, record.error = False, str(e)[:300]
        record.save()
        return items, 0
    record.input_tokens, record.output_tokens = tokens_in, tokens_out
    record.cost_usd = cost(settings.GEMINI_MODEL, tokens_in, tokens_out)

    answers = {a.get("n"): a for a in parsed.get("items", []) if isinstance(a, dict)}
    out, kept = [], 0
    for n, it in enumerate(items, 1):
        answer = answers.get(n)
        problem = check(it, answer, sources) if answer else "missing"
        if problem:
            logger.info("Coach writer dropped item %s: %s", n, problem)
            out.append(it)
            continue
        cited = [str(c) for c in answer["cites"]]
        out.append(
            {
                **it,
                "title": answer["title"].strip(),
                "advice": answer["advice"].strip(),
                "knowledge": [
                    {"id": c, "title": sources[c]["title"]} for c in cited if c.startswith("k:")
                ],
            }
        )
        kept += 1
    record.kept = kept
    record.save()
    return out, kept
