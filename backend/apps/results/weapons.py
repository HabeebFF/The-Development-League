"""Which weapons players knock and kill with, and how often their knocks are headshots.

Every kill and knock in the logs carries a weapon number (knocks get theirs from the replay
.bin); staff name each number once at Staff > Coach > Weapons. Only named weapons count
here, so zone, fall and vehicle numbers (0, -31, 80006...) never show as a "main weapon".
Kills and knocks on team-mates, and self-kills, are left out.

The game marks headshots on knocks only (kills are never flagged), so the headshot rate is
headshot knocks / knocks.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable

from .models import MatchEvent

TOP = 3  # weapons listed per player


def names() -> dict[int, str]:
    from apps.coach.models import WeaponName

    return dict(WeaponName.objects.values_list("weapon_id", "name"))


def hs_pct(headshots: int | None, knocks: int | None) -> int | None:
    """Headshot knocks as a whole percentage of knocks; ``None`` without knocks."""
    if not knocks:
        return None
    return round(100 * (headshots or 0) / knocks)


def _events(match_ids: Iterable[int], players: Iterable[int] | None, team: int | None = None):
    """(player, weapon, kind) for kills and knocks on someone from another team; with
    ``team``, only those made while playing for that team."""
    qs = MatchEvent.objects.filter(
        match_id__in=list(match_ids),
        kind__in=[MatchEvent.Kind.KILL, MatchEvent.Kind.KNOCK],
        actor_player__isnull=False,
        weapon_id__isnull=False,
    )
    if players is not None:
        qs = qs.filter(actor_player_id__in=list(players))
    if team is not None:
        qs = qs.filter(actor_team_id=team)
    fields = ("actor_player_id", "target_player_id", "actor_team_id", "target_team_id")
    for a, t, at, tt, wid, kind in qs.values_list(*fields, "weapon_id", "kind").iterator():
        if a == t or (at is not None and at == tt):
            continue
        yield a, wid, kind


def by_weapon(
    match_ids: Iterable[int], players: Iterable[int] | None = None, team: int | None = None
) -> dict[int, dict[int, dict[str, int]]]:
    """Per player: {weapon id: {"kills": n, "knocks": n}} (named weapons only)."""
    known = names()
    out: dict[int, dict[int, dict[str, int]]] = defaultdict(dict)
    for pid, wid, kind in _events(match_ids, players, team):
        if wid not in known:
            continue
        w = out[pid].setdefault(wid, {"kills": 0, "knocks": 0})
        w["kills" if kind == MatchEvent.Kind.KILL else "knocks"] += 1
    return dict(out)


def counts(match_ids: Iterable[int], players: Iterable[int] | None = None) -> dict[int, Counter]:
    """Per player: {weapon id: kills + knocks} in these matches (named weapons only)."""
    return {
        pid: Counter({wid: n["kills"] + n["knocks"] for wid, n in ws.items()})
        for pid, ws in by_weapon(match_ids, players).items()
    }


def listing(counter: Counter, known: dict[int, str], top: int = TOP) -> list[dict]:
    """The most used weapons first: [{id, name, uses, share}], ``share`` in whole percent."""
    total = sum(counter.values())
    if not total:
        return []
    ranked = sorted(counter.items(), key=lambda kv: (-kv[1], known.get(kv[0], "")))
    return [
        {"id": wid, "name": known.get(wid, f"#{wid}"), "uses": n, "share": round(100 * n / total)}
        for wid, n in ranked[:top]
    ]


def main(counter: Counter | None, known: dict[int, str]) -> dict | None:
    """The most used weapon, or ``None`` when no named weapon was used."""
    first = listing(counter or Counter(), known, top=1)
    return first[0] if first else None


def shooting(
    match_ids: Iterable[int], players: Iterable[int], team: int | None = None
) -> dict[int, dict]:
    """Per player, over these matches: knocks, headshot knocks, headshot rate and the most
    used weapons ([{id, name, kills, knocks, uses, share}], most used first). With ``team``,
    only what they did while playing for that team."""
    from .models import PlayerMatchResult

    match_ids, players = list(match_ids), list(players)
    known = names()
    used = by_weapon(match_ids, players, team)
    out: dict[int, dict] = {
        pid: {"matches": 0, "kills": 0, "knocks": 0, "headshots": 0} for pid in players
    }
    results = PlayerMatchResult.objects.filter(match_id__in=match_ids, player_id__in=players)
    if team is not None:
        results = results.filter(team_id=team)
    for r in results:
        o = out[r.player_id]
        o["matches"] += 1
        o["kills"] += r.kills
        o["knocks"] += r.knocks or 0
        o["headshots"] += r.headshot_knocks or 0
    for pid, o in out.items():
        ws = used.get(pid, {})
        top = listing(Counter({w: n["kills"] + n["knocks"] for w, n in ws.items()}), known)
        o["hs_pct"] = hs_pct(o["headshots"], o["knocks"])
        o["weapons"] = [{**w, **ws[w["id"]]} for w in top]
        o["main_weapon"] = o["weapons"][0] if o["weapons"] else None
    return out
