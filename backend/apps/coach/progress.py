"""Task tracking: is the team actually doing what its weekly report asked?

Each task is turned into a check that one match (or one fight) passes or fails, read from
the fact the task cites ("Rotate earlier into Zone 3 on Kalahari" becomes "inside Zone 3
before it closed, on Kalahari"). The fact also gives the score before the report, so the
week's matches can be compared with it: done, improving, or still a problem.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .engine import SPOT_M, TeamMatch

# A week needs this many checks before it says anything stronger than "too early".
MIN_CHECKS = 2
DONE_RATE = 0.8
IMPROVED_BY = 0.1


def goal_for(task: dict, facts: Sequence[dict]) -> dict | None:
    """What to check in each match for this task (None when no cited fact can be checked)."""
    by_id = {f["id"]: f for f in facts}
    overall = by_id.get("results.placement")
    for fid in task.get("facts", []):
        f = by_id.get(fid)
        if not f:
            continue
        key, d, where = f["id"].split(":")[-1], f.get("data", {}), f.get("map")
        on = f" on {where.title()}" if where else ""
        if key.startswith("rotation.z") and key.endswith(".late"):
            return {
                "kind": "late",
                "zone": d["zone"],
                "map": where,
                "unit": "matches",
                "target": f"Inside Zone {d['zone']} before it closes{on}",
                "before": {"good": f["of"] - f["n"], "of": f["of"]},
            }
        if key.startswith("fights.z") or key.startswith("fights.vs"):
            vs = key.startswith("fights.vs")
            won, lost = d.get("won", 0), d.get("lost", 0)
            return {
                "kind": "vs" if vs else "zonefights",
                "zone": d.get("zone"),
                "opponent": d.get("opponent"),
                "map": where,
                "unit": "fights",
                "target": (
                    f"Win your fights against {d.get('opponent_name')}{on}"
                    if vs
                    else f"Win your fights during Zone {d.get('zone')}{on}"
                ),
                "before": {"good": won, "of": won + lost},
            }
        if key.startswith("deaths.top"):
            return {
                "kind": "die",
                "place": d["place"],
                "x": d["x"],
                "z": d["z"],
                "map": where,
                "unit": "matches",
                "target": f"No deaths at {d['place']}{on}",
                "before": {"good": f["of"] - f["n"], "of": f["of"]},
            }
        if key == "drops.contested":
            return {
                "kind": "contest",
                "map": where,
                "unit": "matches",
                "target": f"Land on an uncontested drop{on}",
                "before": {"good": f["of"] - f["n"], "of": f["of"]},
            }
        if key == "drops.usual" and overall:
            limit = round(overall["value"])
            return {
                "kind": "drop",
                "map": where,
                "placement": limit,
                "unit": "matches",
                "target": f"Place {ordinal(limit)} or better{on}",
                "before": None,
            }
    return None


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def check(goal: dict, m: TeamMatch) -> tuple[int, int]:
    """(passed, checked) for one match: 0 checked when the goal doesn't apply to it."""
    if goal.get("map") and m.map != goal["map"]:
        return 0, 0
    kind = goal["kind"]
    if kind == "late":
        entry = next((e for e in m.entries if e.zone == goal["zone"]), None)
        if entry is None:  # out before that zone closed: nothing to judge
            return 0, 0
        return int(entry.lead_s is not None and entry.lead_s >= 0), 1
    if kind in ("zonefights", "vs"):
        rows = [
            f
            for f in m.fights
            if f.result != "even"
            and (f.zone == goal["zone"] if kind == "zonefights" else f.opponent == goal["opponent"])
        ]
        return sum(1 for f in rows if f.result == "won"), len(rows)
    if kind == "die":
        died = any(
            s.name == goal["place"] or math.hypot(s.x - goal["x"], s.z - goal["z"]) <= SPOT_M
            for s in m.deaths
        )
        return int(not died), 1
    if kind == "contest":
        return (int(not m.contested_by), 1) if m.drop else (0, 0)
    if kind == "drop":
        return int(m.placement <= goal["placement"]), 1
    return 0, 0


def progress(goal: dict, matches: Sequence[TeamMatch]) -> dict:
    """How the team did on a goal over some matches, against its score before."""
    good = of = 0
    used = []
    for m in matches:
        g, n = check(goal, m)
        if n:
            good, of = good + g, of + n
            used.append(m.match)
    before = goal.get("before")
    before_rate = before["good"] / before["of"] if before and before["of"] else None
    rate = good / of if of else None
    if of == 0:
        status = "untested"
    elif of < MIN_CHECKS:
        status = "early"
    elif rate >= DONE_RATE and (before_rate is None or rate > before_rate):
        status = "done"
    elif before_rate is not None and rate >= before_rate + IMPROVED_BY:
        status = "improving"
    elif before_rate is None and rate >= 0.5:
        status = "improving"
    else:
        status = "problem"
    return {
        "target": goal["target"],
        "unit": goal["unit"],
        "good": good,
        "of": of,
        "before": before,
        "status": status,
        "matches": used,
    }


def report_progress(report_tasks: Sequence[dict], facts: Sequence[dict], week: Sequence[TeamMatch]):
    """Each task's progress over the report's week (None for a task that can't be checked)."""
    out = []
    for t in report_tasks:
        goal = goal_for(t, facts)
        out.append(progress(goal, week) if goal else None)
    return out
