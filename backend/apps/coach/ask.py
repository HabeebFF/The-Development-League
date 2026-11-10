"""Ask the coach: answer a team's own question, in plain words, from our facts only.

A question like "How do we beat Solar Flare on Purgatory?" is read for the teams and the
map it names. The answer is built from the same facts the rest of the coach uses: the
asking team's own facts, each named opponent's facts and counter-plan plays, the two
teams' record against each other, and the when-to-rotate advice for the named map.

Like the weekly reports, it works without AI: the template answer lists the strongest
plays and facts that fit the question. When the AI writer is on, it may answer in its
own words, but every point is checked the same way as report tasks before anyone sees
it: it must cite facts it was given, and every number in it must appear in what it
cites. Points that fail are dropped; if none pass, the template answer stands.

The reading and checking functions are plain Python so they can be tested without a
database; ``answer`` loads what it needs.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence

from . import writer

logger = logging.getLogger(__name__)

RULES = "ask-1"
# A question's ``writer`` while the answer is being worked out, and when that failed.
PENDING = "pending"
FAILED = "failed"
LOST = "The coach couldn't work that out. Try asking again."
MIN_QUESTION = 3
MAX_QUESTION = 300
MAX_OPPONENTS = 2
MAX_FACTS = 40
MAX_POINTS = 4
MAX_POINT = 360
MAX_DROPS = 4
# Each point links to at most this many matches (the most recent); the rest are counted.
MAX_POINT_MATCHES = 6

# Words a greeting or small talk is made of. A question made only of these, or one that
# names no team, no map and nothing the coach measures, gets a short "how to ask" reply
# instead of a list of facts.
SMALL_TALK = set(
    "hi hello hey hiya yo sup wassup whats what s up coach good morning afternoon evening"
    " night there how are you u r doing ok okay thanks thank cheers bye please".split()
)
TOPICS = set(
    "beat win won lose lost losing rotate rotation rotations rotating zone zones drop drops"
    " land landing fight fights fighting improve better worse wrong weak weakness weaknesses"
    " strong strength strengths kill kills knock knocks placement place placed booyah style"
    " playstyle aggressive passive play playing tips advice help trade trades third party"
    " push pushing hold edge center centre late early first plan counter against vs versus"
    " map maps team teams opponent opponents well badly mistakes stats do should need focus"
    " practice work".split()
)
HELP = (
    'Ask me about your team, an opponent or a map, for example "How do we beat'
    ' Solar Flare on Purgatory?", "When should we rotate on Bermuda?" or "What are we'
    ' doing wrong?"'
)

SYSTEM = (
    "You are the head coach and analyst of a Free Fire esports squad, answering one of"
    " your own players' questions the way you would in the team's voice chat after scrims:"
    " direct, confident and practical. Speak to the squad as 'you' and 'we'. Lead with the"
    " call (what to do), then the reason from the data in a few words. You are given the"
    " question and numbered facts that a program measured from the league's recorded"
    " matches (the squad's own facts start with 'us/', an opponent's with that opponent's"
    " id, rotation advice with 'rotate/'), plus some general knowledge. Answer in at most 4"
    " short points, each one or two sentences (at most 60 words), the most important first."
    " Use only the facts and knowledge given. Every number you write must appear in a fact"
    " or knowledge entry that point cites. Do not mention places, weapons, characters,"
    " teams or numbers that are not in what you cite. In 'cites', list the ids you used for"
    " that point (at least one fact id). If the facts don't cover part of the question, say"
    " so in 'not_covered' in one sentence with no numbers; otherwise leave it empty."
)

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "points": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "text": {"type": "STRING"},
                    "cites": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["text", "cites"],
            },
        },
        "not_covered": {"type": "STRING"},
    },
    "required": ["points"],
}


# -- Reading the question -----------------------------------------------------------------


def _norm(text: str) -> str:
    """Lower case, letters and digits only, single spaces: 'V-ENT  Esports!' -> 'v ent esports'."""
    return " ".join(re.sub(r"[^0-9a-z]+", " ", text.lower()).split())


def mentions(question: str, labels: dict, *, min_len: int = 2) -> list:
    """Keys of ``labels`` ({key: [names]}) named in the question, in the order they appear.

    Names match whole words only, so the tag 'NF' doesn't match inside 'info'."""
    q = f" {_norm(question)} "
    found: list[tuple[int, int, object]] = []
    for key, names in labels.items():
        best = None
        for name in names:
            n = _norm(name)
            if len(n.replace(" ", "")) < min_len:
                continue
            at = q.find(f" {n} ")
            # The earliest mention wins; on a tie, the longer name (more specific).
            if at >= 0 and (best is None or (at, -len(n)) < best):
                best = (at, -len(n))
        if best is not None:
            found.append((*best, key))
    found.sort(key=lambda f: (f[0], f[1]))
    return [key for _, _, key in found]


def small_talk(question: str) -> bool:
    """True when a question (that names no team or map) isn't about anything we measure."""
    words = set(_norm(question).split())
    if not words or words <= SMALL_TALK:
        return True
    return not words & TOPICS


def trim_matches(points: Sequence[dict], limit: int = MAX_POINT_MATCHES) -> None:
    """Keep each point's most recent matches and count the rest in ``more_matches``."""
    for p in points:
        ms = sorted(p.get("matches", []), reverse=True)
        p["matches"], p["more_matches"] = ms[:limit], max(0, len(ms) - limit)


# -- Gathering the facts --------------------------------------------------------------------


def tag_facts(facts: Sequence[dict], prefix: str) -> list[dict]:
    """Facts with ids prefixed by whose they are ('us/style.label', 'cliq/bermuda:...')."""
    return [{**f, "id": f"{prefix}/{f['id']}"} for f in facts]


def tag_items(items: Sequence[dict], prefix: str) -> list[dict]:
    return [{**it, "facts": [f"{prefix}/{i}" for i in it["facts"]]} for it in items]


def clock(seconds) -> str:
    """Game time as m:ss."""
    s = round(float(seconds))
    return f"{s // 60}:{s % 60:02d}"


def drop_call(d: dict, place: str, map_name: str, first: bool) -> str:
    """A coach's call for one drop: where, when to leave, where to be by when."""
    lead = f"Drop {place}" if first else f"Another option is {place}"
    steps = []
    if d.get("left_s") is not None:
        steps.append(f"leave by {clock(d['left_s'])}")
    inside = {int(k): v for k, v in (d.get("inside_s") or {}).items()}
    zones = [f"Zone {z} by {clock(t)}" for z, t in sorted(inside.items())]
    if zones:
        steps.append("be inside " + " and ".join(zones))
    plan = f", {', then '.join(steps)}" if steps else ""
    return (
        f"{lead} on {map_name}{plan}. That's what the teams who finished top 5 from there did"
        f" (average placement {d['avg_placement']} over {d['team_matches']} team matches)."
    )


def h2h_fact(h2h: dict, prefix: str, opponent: str) -> dict | None:
    """The two teams' record against each other, as a fact the answer can cite."""
    if not h2h.get("met"):
        return None
    met = len(h2h["met"])
    text = f"Against {opponent}: in the same lobby in {met} match{'es' if met != 1 else ''}"
    if h2h["fights"]:
        text += f", {h2h['fights']} fights between the two, won {h2h['won']}, lost {h2h['lost']}"
        call = (
            f"You've fought {opponent} {h2h['fights']} times and won {h2h['won']}"
            f" ({h2h['lost']} lost), across {met} shared lobbies."
            + (" You have the edge: take that fight." if h2h["won"] > h2h["lost"] else "")
            + (" They have your number: don't take even fights with them." if h2h["lost"]
               > h2h["won"] else "")
        )  # fmt: skip
    else:
        text += ", no fights between the two"
        call = f"You've shared {met} lobbies with {opponent} but never fought them yet."
    return {
        "id": f"{prefix}/h2h",
        "topic": "results",
        "text": text,
        "call": call,
        "value": h2h["won"],
        "n": met,
        "of": met,
        "matches": h2h["matches"] or h2h["met"],
        "map": None,
        "data": {"won": h2h["won"], "lost": h2h["lost"], "fights": h2h["fights"]},
    }


def drop_facts(advice: dict, map_slug: str, map_name: str) -> list[dict]:
    """When-to-rotate advice for a map, best drops first, as facts."""
    out = []
    for i, d in enumerate(advice.get("drops", [])[:MAX_DROPS], 1):
        place = d["place"] or "an unnamed spot"
        lines = "; ".join(d["advice"])
        out.append(
            {
                "id": f"rotate/{map_slug}/{i}",
                "topic": "rotation",
                "text": f"Dropping at {place} on {map_name}: average placement"
                f" {d['avg_placement']} over {d['team_matches']} team matches. {lines}",
                "call": drop_call(d, place, map_name, i == 1),
                "value": d["avg_placement"],
                "n": len(d["matches"]),
                "of": len(advice.get("matches", [])) or len(d["matches"]),
                "matches": d["matches"],
                "map": map_slug,
                "data": {"place": place, "left_s": d["left_s"], "inside_s": d["inside_s"]},
            }
        )
    return out


def relevant(facts: Sequence[dict], map_slug: str | None) -> list[dict]:
    """With a map named, that map's facts first, then all-maps facts, and no other map's."""
    if not map_slug:
        return list(facts)
    on_map = [f for f in facts if f.get("map") == map_slug]
    overall = [f for f in facts if not f.get("map")]
    return on_map + overall


# -- The template answer (no AI) ----------------------------------------------------------


ROTATE_WORDS = {
    "rotate",
    "rotation",
    "rotations",
    "rotating",
    "drop",
    "drops",
    "land",
    "landing",
    "zone",
    "zones",
    "when",
    "leave",
}


def about_rotation(question: str) -> bool:
    return bool(set(_norm(question).split()) & ROTATE_WORDS)


def template_points(
    plays: Sequence[dict],
    facts: Sequence[dict],
    *,
    has_opponent: bool,
    tasks: Sequence[dict] = (),
    rotate_first: bool = False,
) -> list[dict]:
    """The answer without AI, in the coach's words: the plays against a named opponent, our
    own biggest fixes (as in the weekly report), the head-to-head record and the best drops
    on a named map, each backed by the facts and matches behind it."""
    by_id = {f["id"]: f for f in facts}

    def item(p: dict) -> dict:
        return {"text": p["title"], "facts": p["facts"], "matches": p["matches"]}

    def called(f: dict) -> dict:
        return {"text": f.get("call", f["text"]), "facts": [f["id"]], "matches": f["matches"]}

    h2h = [called(f) for f in facts if f["id"].endswith("/h2h")]
    drops = [called(f) for f in facts if f["id"].startswith("rotate/")]
    ours = [item(t) for t in tasks]
    points = [item(p) for p in plays] + h2h
    points += drops + ours if rotate_first else ours + drops
    if not has_opponent and not points:
        # Nothing stands out: the facts about us that rest on the most matches.
        rest = sorted(
            (f for f in facts if f["id"].startswith("us/")), key=lambda f: (-f["n"], f["id"])
        )
        points += [called(f) for f in rest]
    out, seen = [], set()
    for p in points:
        if p["text"] in seen or not all(i in by_id for i in p["facts"]):
            continue
        seen.add(p["text"])
        out.append(p)
    return out[:MAX_POINTS]


# -- Checking an AI answer ----------------------------------------------------------------


def check_point(point: dict, sources: dict[str, dict]) -> str | None:
    """Why an AI point can't be shown, or None when it passes."""
    text = str(point.get("text", "")).strip()
    cites = [str(c) for c in point.get("cites", []) if str(c).strip()]
    if not text:
        return "empty"
    if len(text) > MAX_POINT:
        return "too long"
    unknown = [c for c in cites if c not in sources]
    if unknown:
        return f"cites unknown {unknown[0]}"
    if not any(not c.startswith("k:") for c in cites):
        return "cites no fact"
    allowed = set().union(*(writer.source_numbers(sources[c]) for c in cites))
    missing = writer.numbers_in(text) - allowed
    if missing:
        return f"number {sorted(missing)[0]} not in what it cites"
    return None


def checked(parsed: dict, sources: dict[str, dict]) -> tuple[list[dict], str]:
    """The AI points that pass the checks, and its 'not covered' note if it has no numbers."""
    points = []
    for p in parsed.get("points", [])[:MAX_POINTS]:
        if not isinstance(p, dict):
            continue
        problem = check_point(p, sources)
        if problem:
            logger.info("Coach ask dropped a point: %s", problem)
            continue
        cites = [str(c) for c in p["cites"]]
        facts = [c for c in cites if not c.startswith("k:")]
        points.append(
            {
                "text": p["text"].strip(),
                "facts": facts,
                "matches": sorted({m for c in facts for m in sources[c].get("matches", [])}),
                "knowledge": [
                    {"id": c, "title": sources[c]["title"]} for c in cites if c.startswith("k:")
                ],
            }
        )
    note = str(parsed.get("not_covered") or "").strip()
    if writer.numbers_in(note) or len(note) > MAX_POINT:
        note = ""
    return points, note


def ai_answer(
    question: str, team: str, facts: Sequence[dict], *, opponents: Sequence[str], map_name: str
) -> tuple[list[dict], str] | None:
    """Checked AI points (and its not-covered note), or None when the AI can't answer or
    nothing it wrote passed. Every call is recorded in ``AiUsage``."""
    from django.conf import settings

    from .models import AiUsage

    if not facts or writer.unavailable():
        return None
    knowledge = writer.knowledge_for(facts)
    sources = {**{f["id"]: f for f in facts}, **{k["id"]: k for k in knowledge}}
    prompt = json.dumps(
        {
            "question": question,
            "team": team,
            "opponents": list(opponents),
            "map": map_name or None,
            "facts": [{"id": f["id"], "text": f["text"], "map": f.get("map")} for f in facts],
            "knowledge": knowledge,
        }
    )
    record = AiUsage(feature="ask", provider="gemini", model=settings.GEMINI_MODEL, items=1)
    try:
        parsed, tokens_in, tokens_out = writer._gemini(prompt, system=SYSTEM, schema=SCHEMA)
    except writer.WriterError as e:
        logger.warning("Coach ask: %s", e)
        record.ok, record.error = False, str(e)[:300]
        record.save()
        return None
    record.input_tokens, record.output_tokens = tokens_in, tokens_out
    record.cost_usd = writer.cost(settings.GEMINI_MODEL, tokens_in, tokens_out)
    points, note = checked(parsed if isinstance(parsed, dict) else {}, sources)
    record.kept = 1 if points else 0
    record.save()
    return (points, note) if points else None


# -- Putting it together --------------------------------------------------------------------


def understand(question: str, team) -> tuple[list, object | None]:
    """The opponents (Team objects, not the asking team) and the map a question names."""
    from apps.league.models import Team, TeamAlias
    from apps.maps.models import Map

    labels: dict[int, list[str]] = {}
    for t in Team.objects.all():
        labels[t.pk] = [t.name, t.slug.replace("-", " ")] + ([t.tag] if t.tag else [])
    for team_id, name in TeamAlias.objects.values_list("team_id", "in_game_name"):
        labels.setdefault(team_id, []).append(name)
    ids = [i for i in mentions(question, labels) if i != team.pk][:MAX_OPPONENTS]
    teams = Team.objects.in_bulk(ids)
    opponents = [teams[i] for i in ids if i in teams]

    maps = {m.slug: [m.name, m.slug] for m in Map.objects.all()}
    found = mentions(question, maps, min_len=3)
    game_map = Map.objects.filter(slug=found[0]).first() if found else None
    return opponents, game_map


def cached_map_advice(map_slug: str) -> dict:
    """When-to-rotate advice for a map (it reads every match on the map, so it is kept
    for a while and made again once a new match on the map is published)."""
    from django.core.cache import cache

    from apps.league.models import Match

    from .rotate import map_advice

    latest = (
        Match.objects.filter(status=Match.Status.PUBLISHED, map__slug=map_slug)
        .order_by("-pk")
        .values_list("pk", flat=True)
        .first()
    )
    key = f"coach:ask:rotate:{map_slug}:{latest}"
    advice = cache.get(key)
    if advice is None:
        advice = map_advice(map_slug)
        cache.set(key, advice, 6 * 60 * 60)
    return advice


def answer(question: str, team) -> dict:
    """The coach's answer to ``team``'s question, with the facts and matches behind it."""
    from apps.league.models import Match, Team

    from . import counter
    from .engine import load_games, measure, profile
    from .reports import tasks_from

    opponents, game_map = understand(question, team)
    if not opponents and not game_map and small_talk(question):
        return {
            "opponents": [],
            "map": None,
            "points": [],
            "not_covered": HELP,
            "matches": [],
            "writer": "help",
        }
    map_slug = game_map.slug if game_map else None
    map_name = game_map.name if game_map else ""

    # Every published match of the teams involved: the answer is worked out in the
    # background worker, so reading them all is fine.
    ids = set(
        Match.objects.filter(
            status=Match.Status.PUBLISHED, team_results__team__in=[team, *opponents]
        ).values_list("pk", flat=True)
    )
    games = load_games(sorted(ids)) if ids else []
    names = dict(Team.objects.values_list("pk", "name"))

    ours = [measure(g, team.pk) for g in games if team.pk in g.teams]
    own = profile(ours, names)["facts"] if ours else []
    facts = tag_facts(own, "us")
    # Our biggest fixes, picked the same way as the weekly report's tasks.
    tasks = tag_items(tasks_from(relevant(own, map_slug)), "us")
    plays: list[dict] = []
    for o in opponents:
        plan = counter.build(games, team.pk, o.pk, names)
        facts = tag_facts(plan["facts"], o.slug) + facts
        plays += tag_items(plan["plays"], o.slug)
        if h2h := h2h_fact(plan["head_to_head"], o.slug, o.name):
            facts.insert(0, h2h)
    if game_map:
        facts = drop_facts(cached_map_advice(game_map.slug), game_map.slug, game_map.name) + facts

    # Keep the facts that the plays and fixes rest on, then the rest, up to MAX_FACTS.
    cited = {i for p in [*plays, *tasks] for i in p["facts"]}
    rel = relevant(facts, map_slug)
    facts = ([f for f in rel if f["id"] in cited] + [f for f in rel if f["id"] not in cited])[
        :MAX_FACTS
    ]
    kept = {f["id"] for f in facts}
    plays = [p for p in plays if all(i in kept for i in p["facts"])]
    tasks = [t for t in tasks if all(i in kept for i in t["facts"])]

    points = template_points(
        plays,
        facts,
        has_opponent=bool(opponents),
        tasks=tasks,
        rotate_first=about_rotation(question),
    )
    note, used = "", "template"
    if (ai := ai_answer(question, team.name, facts, opponents=[o.name for o in opponents],
                        map_name=map_name)):  # fmt: skip
        points, note = ai
        used = f"{RULES}+{writer.label()}"
    if not points:
        note = note or (
            "There isn't enough recorded data yet to answer that. A pattern needs the same"
            " thing in at least 3 matches."
        )

    trim_matches(points)
    by_id = {f["id"]: f for f in facts}
    for p in points:
        p["why"] = [by_id[i]["text"] for i in p["facts"] if i in by_id]
    match_ids = sorted({m for p in points for m in p["matches"]})
    labels = {g.match: (g.label, g.map) for g in games}
    return {
        "opponents": [{"slug": o.slug, "name": o.name} for o in opponents],
        "map": {"slug": game_map.slug, "name": game_map.name} if game_map else None,
        "points": points,
        "not_covered": note,
        "matches": [
            {
                "id": m,
                "label": labels.get(m, (f"Match {m}", ""))[0],
                "map": labels.get(m, ("", ""))[1],
            }
            for m in match_ids
        ],  # fmt: skip
        "writer": used,
    }
