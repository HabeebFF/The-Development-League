"""When to rotate: for one map, what teams that dropped at each spot did, and when the
ones that placed well left.

All of it is counted from the replay paths: where a team landed, when it first moved away
from its drop, and when it was inside each zone. The advice is the median of the teams
that finished in the top 5 from that drop, with the matches it comes from.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence

from .engine import MIN_MATCHES, Game, Spot, _landing, _spots, area_at, measure

# Moving this far from where the team landed means it has left its drop.
LEFT_M = 250.0
# Placements that count as "did well".
TOP = 5
MAX_ROUTES = 6


def left_drop(path, landing) -> float | None:
    """When the team first got LEFT_M away from where it landed."""
    for seg in path.segments:
        for t, x, z in seg:
            if t > landing[0] and math.hypot(x - landing[1], z - landing[2]) >= LEFT_M:
                return t
    return None


def clock(s: float) -> str:
    return f"{int(s // 60)}:{int(s % 60):02d}"


def _inside_by(game: Game, entries, zone: int) -> float | None:
    """Game time the team was inside ``zone`` (from its lead before the zone closed)."""
    z = next((z for z in game.zones if z.number == zone), None)
    e = next((e for e in entries if e.zone == zone), None)
    if z is None or e is None or e.lead_s is None:
        return None
    return z.closes_s - e.lead_s


def _route(path, until: float | None) -> list[list[list[float]]]:
    segs = path.simplified()
    if until is None:
        return segs
    return [[p for p in seg if p[0] <= until] for seg in segs if seg and seg[0][0] <= until]


def advice(games: Sequence[Game], names: dict[int, str]) -> dict:
    """Drop-by-drop rotation timing on one map (``games`` all on that map)."""
    rows = []  # (spot, match, team, placement, left_s, inside {zone: t}, route)
    for g in games:
        zone3 = next((z.closes_s for z in g.zones if z.number == 3), None)
        for team_id, team in g.teams.items():
            landing = _landing(team.path)
            if landing is None:
                continue
            m = measure(g, team_id)
            rows.append(
                {
                    "spot": Spot(area_at(g.areas, landing[1], landing[2]), landing[1], landing[2]),
                    "match": g.match,
                    "label": g.label,
                    "team": team_id,
                    "placement": team.placement,
                    "left_s": left_drop(team.path, landing),
                    "inside": {k: _inside_by(g, m.entries, k) for k in (1, 2, 3)},
                    "route": _route(team.path, zone3),
                }
            )

    drops = []
    for place, count, mids, (x, z) in _spots((r["spot"], i) for i, r in enumerate(rows)):
        group = [rows[i] for i in mids]
        matches = sorted({r["match"] for r in group})
        if len(matches) < MIN_MATCHES:
            continue
        top = [r for r in group if r["placement"] <= TOP]
        left = [r["left_s"] for r in top if r["left_s"] is not None]
        inside = {
            k: statistics.median(v)
            for k in (2, 3)
            if len(v := [r["inside"][k] for r in top if r["inside"][k] is not None]) >= 2
        }
        lines = []
        if len(left) >= 2:
            lines.append(
                f"Teams that finished top {TOP} from here left by about"
                f" {clock(statistics.median(left))} (median of {len(left)})"
            )
        for k, t in inside.items():
            lines.append(f"They were inside Zone {k} by about {clock(t)}")
        if not top:
            lines.append(f"No team has finished top {TOP} from here yet")
        drops.append(
            {
                "place": place,
                "x": round(x),
                "z": round(z),
                "team_matches": count,
                "matches": matches,
                "avg_placement": round(statistics.fmean(r["placement"] for r in group), 1),
                "top_finishes": len(top),
                "left_s": round(statistics.median(left)) if len(left) >= 2 else None,
                "inside_s": {k: round(t) for k, t in inside.items()},
                "advice": lines,
                "top_matches": sorted({r["match"] for r in top}),
                "routes": [
                    {
                        "team": names.get(r["team"], f"team {r['team']}"),
                        "match": r["match"],
                        "label": r["label"],
                        "placement": r["placement"],
                        "path": r["route"],
                    }
                    for r in sorted(top, key=lambda r: r["placement"])[:MAX_ROUTES]
                ],
            }
        )
    drops.sort(key=lambda d: (d["avg_placement"], -d["team_matches"]))

    # Where the late zones ended up: the last zone of each match, as a circle.
    ends = []
    for g in games:
        if g.zones:
            last = g.zones[-1]
            ends.append(
                {
                    "match": g.match,
                    "label": g.label,
                    "zone": last.number,
                    "x": round(last.x),
                    "z": round(last.z),
                    "r": round(last.r),
                }
            )
    return {
        "matches": [{"id": g.match, "label": g.label} for g in games],
        "zone_ends": ends,
        "drops": drops,
    }


def map_advice(map_slug: str) -> dict:
    from apps.league.models import Match, Team

    from .engine import load_games

    ids = Match.objects.filter(status=Match.Status.PUBLISHED, map__slug=map_slug).values_list(
        "pk", flat=True
    )
    games = load_games(ids)
    return {"map": map_slug, **advice(games, dict(Team.objects.values_list("pk", "name")))}
