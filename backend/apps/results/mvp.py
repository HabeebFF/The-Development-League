"""The MVP of a match: the player with the best match rating (ties: more kills, then more
damage), with the weapons they knocked and killed with and the abilities the replay shows
them using.

The logs don't name an MVP or say which character skills a player had equipped. The replay
file does record a few abilities by their owner (Bolt Maker zones, Dinoculars scans and
player UAVs, see ``apps.rotations``), so those are shown as "seen in the replay".
"""

from __future__ import annotations

from collections import Counter

from apps.league.models import Match
from apps.rotations.models import ReplayObject

from . import weapons
from .models import PlayerMatchRating, PlayerMatchResult


def _media(f) -> str | None:
    return f.url if f else None


def for_match(match: Match) -> dict | None:
    results = {
        r.player_id: r
        for r in PlayerMatchResult.objects.filter(match=match).select_related("player", "team")
    }
    ratings = {
        r.player_id: r.rating
        for r in PlayerMatchRating.objects.filter(match=match, player_id__in=list(results))
    }
    if not results:
        return None

    def key(pid: int) -> tuple:
        r = results[pid]
        return (ratings.get(pid, 0.0), r.kills, r.knocks or 0, r.damage_dealt or 0)

    pid = max(results, key=key)
    r = results[pid]
    if not ratings and not r.kills:
        return None
    used = weapons.by_weapon([match.pk], [pid]).get(pid, {})
    listed = weapons.listing(
        Counter({w: n["kills"] + n["knocks"] for w, n in used.items()}),
        weapons.names(),
        top=10,
    )
    skills = Counter(
        ReplayObject.objects.filter(match=match, player_id=pid).values_list("kind", flat=True)
    )
    labels = dict(ReplayObject.Kind.choices)
    team, player = r.team, r.player
    return {
        "player_id": pid,
        "name": r.display_name or player.display_name,
        "photo": _media(player.photo_cutout) or _media(player.photo),
        "team": {
            "id": team.pk,
            "name": team.name,
            "tag": team.tag,
            "slug": team.slug,
            "logo": _media(team.logo),
            "primary_color": team.primary_color,
        },
        "rating": ratings.get(pid),
        "kills": r.kills,
        "knocks": r.knocks,
        "headshots": r.headshot_knocks,
        "hs_pct": weapons.hs_pct(r.headshot_knocks, r.knocks),
        "damage": r.damage_dealt,
        "weapons": [{**w, **used[w["id"]]} for w in listed],
        "skills": [
            {"kind": kind, "label": labels.get(kind, kind), "count": n}
            for kind, n in skills.most_common()
        ],
    }
