"""Counter plans: how to play against one opponent, from that opponent's own matches.

Each *play* is a sentence built from the opponent's facts (the same facts a weekly report
uses), plus the two teams' record against each other. Like report tasks, every play names
the facts and matches behind it, so nothing in a plan is made up.
"""

from __future__ import annotations

from collections.abc import Sequence

from .engine import Game, measure, profile

# A pattern needs to show up in this share of the opponent's matches to become a play.
PATTERN_SHARE = 0.4
MAX_PLAYS = 6
# Bumped when the rules change, so plans saved earlier in the week are made again.
RULES = "template-1"


def _where(fact: dict) -> str:
    return f" on {fact['map'].title()}" if fact.get("map") else ""


def plays_from(facts: Sequence[dict], opponent: str) -> list[dict]:
    """Plays against a team, from that team's facts. Strongest evidence first."""
    out: list[tuple[float, str, dict]] = []

    def play(score, key, title, *cited):
        cited = [c for c in cited if c]
        # The same pattern overall and on one map: the one true more often wins.
        share = cited[0]["n"] / max(1, cited[0]["of"])
        out.append(
            (
                score + share / 100,
                key,
                {
                    "title": title,
                    "why": [c["text"] for c in cited],
                    "facts": [c["id"] for c in cited],
                    "matches": sorted({m for c in cited for m in c["matches"]}),
                },
            )
        )

    for f in facts:
        key = f["id"].split(":")[-1]
        d = f.get("data", {})
        where = _where(f)
        if key == "drops.usual":
            play(
                f["value"] * f["n"],
                f"drop:{f.get('map')}",
                f"Expect {opponent} at {d['place']}{where}: plan your drop and first rotation"
                " around them",
                f,
            )
        elif key.startswith("rotation.z") and key.endswith(".late") and f["value"] >= PATTERN_SHARE:
            play(
                f["value"] * f["n"] + 1,
                f"late{d['zone']}",
                f"They reach Zone {d['zone']} late{where}: hold the edge they rotate through"
                " and catch them in the open",
                f,
            )
        elif key.startswith("fights.z") and d.get("lost", 0) > d.get("won", 0):
            play(
                d["lost"] / max(1, d["won"] + d["lost"]) * f["n"] + 1,
                f"zonefights{d['zone']}",
                f"They lose more fights than they win during Zone {d['zone']}{where}:"
                " that's the time to push them",
                f,
            )
        elif key == "style.label":
            style = f["text"].rsplit(" ", 1)[-1]
            fights = next((x for x in facts if x["id"] == f["id"].replace("label", "fights")), None)
            if style == "aggressive":
                play(
                    f["n"] / 2,
                    "style",
                    f"They start most fights{where}: don't give them easy first knocks,"
                    " move between cover and keep Gloo Walls ready",
                    f,
                    fights,
                )
            elif style == "passive":
                play(
                    f["n"] / 2,
                    "style",
                    f"They avoid fights{where}: you can take space near them, and they"
                    " rarely punish a rotation",
                    f,
                    fights,
                )
        elif key == "position.edge":
            if f["value"] < 0.5:
                title = f"They hold the centre of the zone{where}: don't run into it late"
            elif f["value"] > 0.75:
                title = (
                    f"They play the edge of the zone{where}:"
                    " check behind you when you rotate along it"
                )
            else:
                continue
            play(f["n"] / 2, "edge", title, f)
        elif key == "deaths.top1":
            play(
                f["n"] / 2,
                f"die:{d['place']}",
                f"They often fall at {d['place']}{where}: a good place to set up against them",
                f,
            )
    # Early rotations: one play listing the zones, for the scope (all maps or one map) that
    # has the most of them.
    early: dict[str | None, list[dict]] = {}
    for f in facts:
        if f["id"].endswith(".early"):
            early.setdefault(f.get("map"), []).append(f)
    if early:
        rows = max(early.values(), key=len)
        zones = [r["id"].split(":")[-1].split(".")[1][1:] for r in rows]
        listed = zones[0] if len(zones) == 1 else ", ".join(zones[:-1]) + f" and {zones[-1]}"
        play(
            max(r["value"] * r["n"] for r in rows),
            "early",
            f"They rotate early into Zone{'s' if len(zones) > 1 else ''} {listed}{_where(rows[0])}:"
            " expect the centre to be taken, plan your own way in",
            *rows,
        )

    best: dict[str, tuple[float, dict]] = {}
    for score, key, p in out:
        if key not in best or score > best[key][0]:
            best[key] = (score, p)
    return [p for _, p in sorted(best.values(), key=lambda sp: -sp[0])][:MAX_PLAYS]


def head_to_head(games: Sequence[Game], team_id: int, opponent_id: int) -> dict:
    """The two teams' fights against each other, from our side."""
    rows = []
    for g in games:
        if team_id in g.teams and opponent_id in g.teams:
            for f in measure(g, team_id).fights:
                if f.opponent == opponent_id:
                    rows.append((g.match, f))
    won = sum(1 for _, f in rows if f.result == "won")
    lost = sum(1 for _, f in rows if f.result == "lost")
    met = sorted({g.match for g in games if team_id in g.teams and opponent_id in g.teams})
    return {
        "met": met,
        "fights": len(rows),
        "won": won,
        "lost": lost,
        "matches": sorted({mid for mid, _ in rows}),
    }


def build(games: Sequence[Game], team_id: int, opponent_id: int, names: dict[int, str]) -> dict:
    theirs = sorted((g for g in games if opponent_id in g.teams), key=lambda g: g.match)
    played = [measure(g, opponent_id) for g in theirs]
    facts = profile(played, names)["facts"]
    opponent = names.get(opponent_id, f"team {opponent_id}")
    return {
        "matches": [{"id": g.match, "label": g.label, "map": g.map} for g in theirs],
        "facts": facts,
        "plays": plays_from(facts, opponent),
        "head_to_head": head_to_head(games, team_id, opponent_id),
        "writer": RULES,
    }
