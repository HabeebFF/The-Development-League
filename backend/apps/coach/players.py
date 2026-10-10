"""Player cards: how each player on a team plays, and one thing for them to work on.

Per match, each player gets a row of plain counts (``match_rows``), stored with the team's
after-match review. A card adds a player's rows up over a period and compares them with
every player in the league over the same matches (``cards``). Like the rest of the coach,
it is arithmetic over what the logs recorded; no AI.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence

from apps.rotations.paths import landed_index

from .engine import Game
from .moments import (
    ALONE_M,
    LEAD_S,
    TRADE_S,
    Player,
    clock,
    downs,
    nearest_mate,
    position,
    standing,
    where_down,
)

TRADE_RANGE_M = 80.0  # a teammate went down this close: a chance to trade
SPACING_EVERY_S = 5.0  # how often a player's distance from the team is sampled
MIN_SAMPLES = 6  # fewer samples than this: no spacing for that match
# A card claims something only with this much behind it.
MIN_DOWNS = 3
MIN_CHANCES = 4
MIN_MATCHES = 4
MIN_FAR_MATCHES = 3
GAP = 0.15  # this far from the league rate (15 points) counts as a real difference
MAX_CLIPS = 3

UTILITY = {
    "PLAYER_UAV": "uav",
    "GENERAL_UAV": "uav",
    "BOLT_MAKER": "bolt",
    "DINOCULARS": "scan",
}


# -- One match ------------------------------------------------------------------------------


def match_rows(
    game: Game,
    team_id: int,
    players: dict[int, Player],
    objects: Iterable[tuple[int | None, str]] = (),
) -> list[dict]:
    """One row of counts per player of ``team_id`` in this match."""
    mates = [e for e, p in players.items() if p.team == team_id]
    ours = [d for d in downs(game.hits) if d.team == team_id]
    hits = sorted(game.hits, key=lambda h: h.t)
    used = Counter((owner, UTILITY.get(kind)) for owner, kind in objects if UTILITY.get(kind))

    rows = []
    for e in mates:
        me = players[e]
        mine = [h for h in hits if h.actor == e and h.actor_team == team_id != h.target_team]
        kills = [h for h in mine if h.kind == "KILL"]

        alone, known, alone_t = 0, 0, []
        for d in (d for d in ours if d.victim == e):
            gap = nearest_mate(e, d.t, where_down(d, players), mates, players, ours)
            if gap is None:
                continue
            known += 1
            if gap > ALONE_M:
                alone += 1
                alone_t.append(d.t)

        chances, trades, missed_t = 0, 0, []
        for d in ours:
            if d.victim == e or not standing(e, d.t, players, ours):
                continue
            spot, here = where_down(d, players), position(me.track, d.t, 1.0)
            if spot is None or here is None:
                continue
            if math.hypot(spot[0] - here[0], spot[1] - here[1]) > TRADE_RANGE_M:
                continue
            chances += 1
            if any(d.t <= h.t <= d.t + TRADE_S and h.target_team == d.by for h in mine):
                trades += 1
            else:
                missed_t.append(d.t)

        spacing, alive_s = _spacing(e, players, mates, ours)
        first = ours[0].victim == e if ours else False
        rows.append(
            {
                "entity": e,
                "player": me.player_id,
                "name": me.name,
                "kills": len(kills),
                "knocks": sum(1 for h in mine if h.kind == "KNOCK"),
                # 0 and below are no weapon (zone, fall, vehicle, or a kill the game logged blank).
                "weapons": dict(Counter(str(h.weapon) for h in kills if (h.weapon or 0) > 0)),
                "downs": sum(1 for d in ours if d.victim == e),
                "known_downs": known,
                "alone_downs": alone,
                "trade_chances": chances,
                "trades": trades,
                "first_down": first,
                "spacing_m": round(statistics.median(spacing), 1) if spacing else None,
                "far": sum(1 for g in spacing if g > ALONE_M),
                "samples": len(spacing),
                "alive_s": alive_s,
                "utility": {k: n for (owner, k), n in used.items() if owner == e},
                "clips": {
                    "alone": [round(t, 1) for t in alone_t],
                    "missed_trade": [round(t, 1) for t in missed_t],
                    "first_down": [round(ours[0].t, 1)] if first else [],
                },
            }
        )
    return rows


def _spacing(e, players, mates, ours) -> tuple[list[float], float | None]:
    """Distances to the nearest standing teammate, sampled from landing until the player's
    last recorded moment; and that last moment (game seconds)."""
    track = players[e].track
    if track is None or not any(track.points):
        return [], None
    last = max(i for i, p in enumerate(track.points) if p is not None)
    alive_s = round(track.start_s + last * track.step_s, 1)
    t = track.start_s + landed_index(track) * track.step_s
    out = []
    while t <= alive_s:
        if standing(e, t, players, ours):
            gap = nearest_mate(e, t, position(track, t, 1.0), mates, players, ours)
            if gap is not None:
                out.append(gap)
        t += SPACING_EVERY_S
    return (out if len(out) >= MIN_SAMPLES else []), alive_s


# -- Cards over a period --------------------------------------------------------------------


def _key(row: dict) -> str:
    """The same player across matches: their account, else their in-game name."""
    if row.get("player"):
        return f"p{row['player']}"
    return f"n{row['name']}" if row.get("name") else f"m{row['match']}e{row['entity']}"


def _add_up(rows: Sequence[dict]) -> dict:
    total = defaultdict(int)
    weapons, utility = Counter(), Counter()
    spacing, alive = [], []
    for r in rows:
        for k in ("kills", "knocks", "downs", "known_downs", "alone_downs", "trade_chances",
                  "trades", "far", "samples"):  # fmt: skip
            total[k] += r.get(k) or 0
        total["first_downs"] += 1 if r.get("first_down") else 0
        weapons.update({int(w): n for w, n in r.get("weapons", {}).items()})
        utility.update(r.get("utility", {}))
        if r.get("spacing_m") is not None:
            spacing.append(r["spacing_m"])
        if r.get("alive_s") is not None:
            alive.append(r["alive_s"])
    total["matches"] = len({r["match"] for r in rows})
    return {
        **total,
        "weapons": weapons,
        "utility": dict(utility),
        "spacing_m": round(statistics.median(spacing)) if spacing else None,
        "alive_s": round(statistics.fmean(alive)) if alive else None,
    }


def _rate(k: int, n: int, bar: int) -> float | None:
    return round(k / n, 3) if n >= bar else None


def _rates(t: dict) -> dict:
    return {
        "alone": _rate(t["alone_downs"], t["known_downs"], MIN_DOWNS),
        "trade": _rate(t["trades"], t["trade_chances"], MIN_CHANCES),
        # Spacing is sampled all match long, so one match has plenty of samples: it needs
        # a few matches as well.
        "far": _rate(t["far"], t["samples"], 1) if t["matches"] >= MIN_FAR_MATCHES else None,
        "first": _rate(t["first_downs"], t["matches"], MIN_MATCHES),
    }


def _pct(x: float | None) -> str:
    return f"{round(x * 100)}%" if x is not None else "n/a"


def cards(
    team_rows: Sequence[dict],
    league_rows: Sequence[dict],
    labels: dict[int, str],
    weapon_names: dict[int, str],
) -> dict:
    """Each player's card, and the league rates they are compared with.

    Every row carries ``match`` (the match id) besides the counts from ``match_rows``.
    """
    league = _rates(_add_up(league_rows)) if league_rows else _rates(_add_up([]))
    by_player: dict[str, list[dict]] = defaultdict(list)
    for r in team_rows:
        by_player[_key(r)].append(r)

    out = []
    for rows in by_player.values():
        rows = sorted(rows, key=lambda r: r["match"])
        t = _add_up(rows)
        rates = _rates(t)
        out.append(
            {
                "player": rows[-1].get("player"),
                "name": rows[-1]["name"] or "Unknown player",
                "matches": t["matches"],
                "kills": t["kills"],
                "knocks": t["knocks"],
                "kills_per_match": round(t["kills"] / t["matches"], 1) if t["matches"] else 0,
                "downs": t["downs"],
                "alone_downs": t["alone_downs"],
                "known_downs": t["known_downs"],
                "trades": t["trades"],
                "trade_chances": t["trade_chances"],
                "first_downs": t["first_downs"],
                "spacing_m": t["spacing_m"],
                "alive_s": t["alive_s"],
                "alive_clock": clock(t["alive_s"]) if t["alive_s"] is not None else None,
                "rates": rates,
                "weapons": [
                    {"name": weapon_names.get(w, f"Weapon {w}"), "kills": n}
                    for w, n in t["weapons"].most_common(3)
                ],
                "utility": t["utility"],
                "task": _task(t, rates, league, rows, labels),
                "strengths": _strengths(t, rates, league),
            }
        )
    out.sort(key=lambda c: (-c["matches"], -c["kills"], c["name"]))
    return {"league": league, "players": out}


def _clips(rows: Sequence[dict], kind: str, labels: dict[int, str]) -> list[dict]:
    found = [(r["match"], t) for r in rows for t in r.get("clips", {}).get(kind, [])]
    found.sort(key=lambda x: (-x[0], x[1]))  # latest matches first
    return [
        {
            "match": m,
            "label": labels.get(m, f"Match {m}"),
            "t": t,
            "clock": clock(t),
            "watch_s": round(max(0.0, t - LEAD_S), 1),
        }
        for m, t in found[:MAX_CLIPS]
    ]


def _task(t, rates, league, rows, labels) -> dict | None:
    """The one thing the numbers say this player should work on (None: nothing stands out)."""
    options = []
    if (r := rates["alone"]) is not None and league["alone"] is not None:
        if t["alone_downs"] >= MIN_DOWNS and r >= max(0.4, league["alone"] + GAP):
            options.append(
                (
                    r - league["alone"],
                    "Stay close to your team",
                    f"You went down more than {round(ALONE_M)} m from the nearest teammate in "
                    f"{t['alone_downs']} of {t['known_downs']} downs. League average: "
                    f"{_pct(league['alone'])}.",
                    "alone",
                )
            )
    if (r := rates["trade"]) is not None and league["trade"] is not None:
        if r <= league["trade"] - GAP:
            options.append(
                (
                    league["trade"] - r,
                    "Swing back when a teammate goes down",
                    f"When a teammate went down within {round(TRADE_RANGE_M)} m of you, you "
                    f"knocked one of the attackers back within {round(TRADE_S)} s "
                    f"{t['trades']} of {t['trade_chances']} times. League average: "
                    f"{_pct(league['trade'])}.",
                    "missed_trade",
                )
            )
    if (r := rates["first"]) is not None and league["first"] is not None:
        if r >= max(0.4, league["first"] + GAP):
            options.append(
                (
                    r - league["first"],
                    "Survive the first contact",
                    f"You were your team's first player down in {t['first_downs']} of "
                    f"{t['matches']} matches. League average: {_pct(league['first'])}.",
                    "first_down",
                )
            )
    if (r := rates["far"]) is not None and league["far"] is not None:
        if r >= max(0.35, league["far"] + GAP):
            options.append(
                (
                    r - league["far"],
                    "Play closer to your squad",
                    f"You spent {_pct(r)} of your time more than {round(ALONE_M)} m from the "
                    f"nearest teammate. League average: {_pct(league['far'])}.",
                    "alone",
                )
            )
    if not options:
        return None
    _, title, why, clips = max(options, key=lambda o: o[0])
    return {"title": title, "why": why, "clips": _clips(rows, clips, labels)}


def _strengths(t, rates, league) -> list[str]:
    out = []
    if (r := rates["trade"]) is not None and league["trade"] is not None:
        if r >= league["trade"] + GAP:
            out.append(
                f"Trades fast: knocked back {t['trades']} of {t['trade_chances']} times "
                f"(league {_pct(league['trade'])})"
            )
    if (r := rates["alone"]) is not None and league["alone"] is not None:
        if r <= league["alone"] - GAP:
            out.append(
                f"Rarely caught alone: {t['alone_downs']} of {t['known_downs']} downs "
                f"(league {_pct(league['alone'])})"
            )
    return out[:2]
