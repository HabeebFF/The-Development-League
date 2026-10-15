"""Damage dealt and taken per player, from the hits in a match's replay .bin.

Every hit is in the replay (type 106, see ``replay_bin``): who hit whom, how hard, with
what. Damage dealt and taken count hits between enemies only; hits on a team-mate are
left out, and hits whose attacker is the victim (zone, falls, a player's own explosive)
are counted separately as zone damage.

A replay that is missing hits would make some players look as if they did no damage, so
each match is checked first: every death should have damage on the dying player shortly
before it. When fewer than ``MIN_COVERAGE`` of the deaths do, the match gets no damage
numbers at all rather than wrong ones.
"""

from __future__ import annotations

from collections import Counter

from apps.ingest.parsers import replay_bin
from apps.league.models import Match

from .models import MatchDamage, MatchEvent, PlayerMatchResult

LOOKBACK_S = 30.0  # a death should have damage on the player in this window before it
MIN_COVERAGE = 0.9

Hit = tuple[float, int, int, int, int, int]  # t, attacker, victim, damage, weapon, part


def same_team(a: int, b: int) -> bool:
    return a >> 24 == b >> 24  # the top byte of an entity id is its team slot


def coverage(hits: list[Hit], deaths: list[tuple[float, int]]) -> float | None:
    """Share of ``deaths`` (time, victim) with enemy damage on the victim just before."""
    if not deaths:
        return None
    taken: dict[int, list[float]] = {}
    for t, a, v, dmg, _w, _p in hits:
        if a != v and not same_team(a, v) and dmg > 0:
            taken.setdefault(v, []).append(t)
    ok = sum(1 for t, v in deaths if any(t - LOOKBACK_S <= h <= t + 1 for h in taken.get(v, [])))
    return ok / len(deaths)


def totals(hits: list[Hit]) -> tuple[Counter, Counter, Counter]:
    """Damage dealt, taken (from enemies) and zone damage, per entity."""
    dealt, taken, zone = Counter(), Counter(), Counter()
    for _t, a, v, dmg, _w, _p in hits:
        if a == v:
            zone[v] += dmg
        elif not same_team(a, v):
            dealt[a] += dmg
            taken[v] += dmg
    return dealt, taken, zone


def build_damage(match: Match, data: bytes) -> str | None:
    """Store the match's damage from its replay ``data``. Returns a warning, or None."""
    hits = replay_bin.parse_hits(data)
    deaths = [
        (e.game_time_s, e.target_entity)
        for e in MatchEvent.objects.filter(
            match=match,
            kind=MatchEvent.Kind.KILL,
            game_time_s__isnull=False,
            target_entity__isnull=False,
        )  # fmt: skip
        if e.actor_entity != e.target_entity
    ]
    share = coverage(hits, deaths)
    results = list(PlayerMatchResult.objects.filter(match=match))
    if not hits or (share is not None and share < MIN_COVERAGE):
        clear_damage(match, results)
        if not hits:
            return None
        return (
            f"Replay .bin is missing hits (only {share:.0%} of deaths have damage before "
            "them), so this match shows no damage."
        )
    dealt, taken, zone = totals(hits)
    for r in results:
        if r.entity_id is None:
            r.damage_dealt = r.damage_taken = r.zone_damage = None
            continue
        r.damage_dealt = dealt[r.entity_id]
        r.damage_taken = taken[r.entity_id]
        r.zone_damage = zone[r.entity_id]
    PlayerMatchResult.objects.bulk_update(results, ["damage_dealt", "damage_taken", "zone_damage"])
    enemy = [
        [round(t, 2), a, v, dmg]
        for t, a, v, dmg, _w, _p in sorted(hits)
        if a != v and not same_team(a, v)
    ]
    MatchDamage.objects.update_or_create(match=match, defaults={"hits": enemy})
    return None


def clear_damage(match: Match, results: list[PlayerMatchResult] | None = None) -> None:
    results = results if results is not None else list(match.player_results.all())
    for r in results:
        r.damage_dealt = r.damage_taken = r.zone_damage = None
    PlayerMatchResult.objects.bulk_update(results, ["damage_dealt", "damage_taken", "zone_damage"])
    MatchDamage.objects.filter(match=match).delete()
