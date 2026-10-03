"""Weekly reports written from facts by fixed rules (no AI): each task names the facts and
matches behind it. A later step lets an AI reword them; the evidence stays the same."""

from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Sequence
from datetime import date, timedelta

from .engine import MIN_MATCHES, Game, TeamMatch, measure, profile

MAX_TASKS = 5
# Changes smaller than these aren't worth reporting.
PLACEMENT_STEP = 1.0
SHARE_STEP = 0.15


def week_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _where(fact: dict) -> str:
    return f" on {fact['map'].title()}" if fact.get("map") else ""


def tasks_from(facts: Sequence[dict]) -> list[dict]:
    """3 to 5 tasks, the biggest problems first. Fewer when the data doesn't show more."""
    by_id = {f["id"]: f for f in facts}
    candidates: list[tuple[float, str, dict]] = []  # score, dedupe key, task

    def task(score, key, title, *cited):
        cited = [c for c in cited if c]
        matches = sorted({m for c in cited for m in c["matches"]})
        candidates.append(
            (
                score,
                key,
                {
                    "title": title,
                    "why": [c["text"] for c in cited],
                    "facts": [c["id"] for c in cited],
                    "matches": matches,
                },
            )
        )

    for f in facts:
        key = f["id"].split(":")[-1]
        d = f.get("data", {})
        where = _where(f)
        prefix = f"{f['map']}:" if f.get("map") else ""
        if key.startswith("rotation.z") and key.endswith(".late") and f["value"] >= 0.4:
            zone = d["zone"]
            lead = by_id.get(f"{prefix}rotation.z{zone}.lead")
            task(
                f["value"] * f["n"],
                f"late{zone}",
                f"Rotate earlier into Zone {zone}{where}",
                f,
                lead,
            )
        elif key.startswith("fights.z") and d.get("lost", 0) > d.get("won", 0):
            task(
                d["lost"] / max(1, d["won"] + d["lost"]) * f["n"],
                f"zonefights{d['zone']}",
                f"Pick your fights during Zone {d['zone']}{where}: you lose more than you win",
                f,
            )
        elif key.startswith("fights.vs") and d.get("lost", 0) >= 2 * max(1, d.get("won", 0)):
            task(
                d["lost"] / max(1, d["won"] + d["lost"]) * f["n"],
                f"vs{d['opponent']}",
                f"Have a plan for {d['opponent_name']}{where}",
                f,
            )
        elif key in ("deaths.top1", "deaths.top2") and f["n"] >= MIN_MATCHES:
            task(
                f["n"] / f["of"] * f["n"],
                f"die{d['place']}",
                f"Stop dying at {d['place']}{where}",
                f,
            )
        elif key == "drops.contested" and f["value"] >= 0.4:
            task(
                f["value"] * f["n"],
                f"contest{f.get('map')}",
                f"Stop contesting your drop{where} with {d['rival_name']}",
                f,
            )
        elif key == "drops.usual":
            overall = by_id.get("results.placement")
            if overall and d["placement"] - overall["value"] >= 2:
                task(
                    (d["placement"] - overall["value"]) * f["n"] / 2,
                    f"drop{f.get('map')}",
                    f"Rethink your usual drop{where}",
                    f,
                    overall,
                )

    best: dict[str, tuple[float, dict]] = {}
    for score, key, t in candidates:
        if key not in best or score > best[key][0]:
            best[key] = (score, t)
    # One task per opponent and one per death spot would crowd out everything else.
    out, used = [], Counter()
    for key, (_, t) in sorted(best.items(), key=lambda kv: -kv[1][0]):
        kind = "vs" if key.startswith("vs") else "die" if key.startswith("die") else key
        if used[kind] >= 1:
            continue
        used[kind] += 1
        out.append(t)
    return out[:MAX_TASKS]


def _metrics(ms: Sequence[TeamMatch]) -> dict[str, float | None]:
    entries = [e for m in ms for e in m.entries]
    fights = [f for m in ms for f in m.fights]
    return {
        "placement": statistics.fmean(m.placement for m in ms) if ms else None,
        "late": (
            sum(1 for e in entries if e.lead_s is None or e.lead_s < 0) / len(entries)
            if entries
            else None
        ),
        "wins": sum(1 for f in fights if f.result == "won") / len(fights) if fights else None,
    }


def changes(recent: Sequence[TeamMatch], earlier: Sequence[TeamMatch]) -> list[dict]:
    """What changed this week against the weeks before (needs 2+ matches on each side)."""
    if len(recent) < 2 or len(earlier) < 2:
        return []
    now, before = _metrics(recent), _metrics(earlier)
    side = f"this week ({len(recent)} matches) against before ({len(earlier)} matches)"
    out = []
    if now["placement"] is not None and before["placement"] is not None:
        diff = before["placement"] - now["placement"]
        if abs(diff) >= PLACEMENT_STEP:
            out.append(
                {
                    "text": f"Average placement {'improved' if diff > 0 else 'dropped'}"
                    f" from {before['placement']:.1f} to {now['placement']:.1f}, {side}",
                    "better": diff > 0,
                }
            )
    if now["late"] is not None and before["late"] is not None:
        diff = before["late"] - now["late"]
        if abs(diff) >= SHARE_STEP:
            out.append(
                {
                    "text": f"Late into the zone {round(now['late'] * 100)}% of the time,"
                    f" {'down' if diff > 0 else 'up'} from {round(before['late'] * 100)}%, {side}",
                    "better": diff > 0,
                }
            )
    if now["wins"] is not None and before["wins"] is not None:
        diff = now["wins"] - before["wins"]
        if abs(diff) >= SHARE_STEP:
            out.append(
                {
                    "text": f"Won {round(now['wins'] * 100)}% of fights,"
                    f" {'up' if diff > 0 else 'down'} from {round(before['wins'] * 100)}%, {side}",
                    "better": diff > 0,
                }
            )
    ids = [m.match for m in recent] + [m.match for m in earlier]
    for c in out:
        c["matches"] = sorted(ids)
    return out


def build(team_id: int, week_start: date, games: Sequence[Game], names: dict[int, str]) -> dict:
    """Report contents for one team, using every match played up to the end of that week."""
    week_end = week_start + timedelta(days=7)
    played = [
        (g, measure(g, team_id))
        for g in games
        if team_id in g.teams and (g.played_on is None or g.played_on < week_end)
    ]
    ms = [m for _, m in played]
    result = profile(ms, names)
    recent = [m for m in ms if m.played_on and m.played_on >= week_start]
    earlier = [m for m in ms if m.played_on and m.played_on < week_start]
    return {
        "matches": [
            {"id": g.match, "label": g.label, "map": g.map, "played_on": g.played_on}
            for g, _ in played
        ],
        "facts": result["facts"],
        "tasks": tasks_from(result["facts"]),
        "changes": changes(recent, earlier),
    }


def write_reports(week_start: date, team_ids: Sequence[int] | None = None) -> int:
    """Create or refresh the template reports for a week. Returns how many were written.
    Reports staff have edited are left alone."""
    from apps.league.models import Team

    from .engine import load_games
    from .models import CoachReport

    games = load_games()
    names = dict(Team.objects.values_list("pk", "name"))
    teams = Team.objects.filter(is_league_member=True)
    if team_ids is not None:
        teams = teams.filter(pk__in=team_ids)
    written = 0
    for team in teams:
        if not any(team.pk in g.teams for g in games):
            continue
        existing = CoachReport.objects.filter(team=team, week_start=week_start).first()
        if existing and existing.edited_by_id:
            continue
        content = build(team.pk, week_start, games, names)
        for m in content["matches"]:
            m["played_on"] = m["played_on"].isoformat() if m["played_on"] else None
        CoachReport.objects.update_or_create(
            team=team, week_start=week_start, defaults={**content, "writer": "template"}
        )
        written += 1
    return written
