"""A team's full roster for its public page: who plays for it now, with their photo, latest
card and numbers for this team this season, and who has left.

Who is on it:
- everyone on the team's roster this season (staff keep it at Staff > Teams), and
- anyone the match logs last saw playing for the team, even if staff haven't added them,
  so a roster is never empty just because nobody typed it in.

Former players are roster entries that have ended, plus anyone who played for the team this
season but has since been seen playing for another team.

Numbers count only published matches the player played for this team in the active season
(every published match when there is no active season).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from django.utils import timezone

from apps.league.models import Match, Player, RosterEntry, Season, Team

from .models import PlayerCard, PlayerMatchRating, PlayerMatchResult
from .weapons import shooting


def _media(f) -> str | None:
    return f.url if f else None


def _latest_cards(player_ids: list[int]) -> dict[int, PlayerCard]:
    """Each player's newest card that is already out (cards come out after their week)."""
    from .cards import release_of

    now = timezone.now()
    out: dict[int, PlayerCard] = {}
    for c in PlayerCard.objects.filter(player_id__in=player_ids, player__hide_card=False).order_by(
        "player_id", "-week"
    ):
        if c.player_id not in out and release_of(c.week) <= now:
            out[c.player_id] = c
    return out


def _card_ref(card: PlayerCard | None) -> dict | None:
    from .cards import ROLE_LABELS, tier

    if card is None:
        return None
    return {
        "overall": card.overall,
        "tier": tier(card.overall),
        "role": card.role,
        "role_label": ROLE_LABELS.get(card.role, card.role),
        "week": card.week,
    }


def roster(team: Team) -> dict:
    season = Season.objects.filter(is_active=True).first()
    results = PlayerMatchResult.objects.filter(team=team, match__status=Match.Status.PUBLISHED)
    if season is not None:
        results = results.filter(match__match_day__stage__season=season)
    played: dict[int, list[int]] = defaultdict(list)
    for pid, mid in results.values_list("player_id", "match_id"):
        played[pid].append(mid)

    entries = (
        list(RosterEntry.objects.filter(team=team, season=season).select_related("player"))
        if season
        else []
    )
    active = {e.player_id: e for e in entries if e.left_on is None}
    ended = {e.player_id: e for e in entries if e.left_on is not None and e.player_id not in active}
    # Players the logs last saw on this team (Player.current_team is set on every upload).
    from_logs = Player.objects.filter(current_team=team).exclude(pk__in=active)
    now_ids = [*active, *from_logs.values_list("pk", flat=True)]
    gone_ids = [p for p in [*ended, *played] if p not in now_ids]
    gone_ids = list(dict.fromkeys(gone_ids))

    players = Player.objects.in_bulk([*now_ids, *gone_ids])
    cards = _latest_cards(now_ids)
    numbers = shooting({m for ms in played.values() for m in ms}, now_ids, team.pk)
    ratings: dict[int, list[float]] = defaultdict(list)
    for pid, mid, value in PlayerMatchRating.objects.filter(
        player_id__in=now_ids, match_id__in={m for ms in played.values() for m in ms}
    ).values_list("player_id", "match_id", "rating"):
        if mid in played.get(pid, ()):
            ratings[pid].append(value)
    damage: dict[int, int | None] = {}
    for pid, dealt in results.filter(player_id__in=now_ids).values_list(
        "player_id", "damage_dealt"
    ):
        if dealt is not None:
            damage[pid] = (damage.get(pid) or 0) + dealt

    def ref(p: Player) -> dict:
        return {"id": p.pk, "game_uid": str(p.game_uid), "display_name": p.display_name}

    current = []
    for pid in now_ids:
        p, e, n = players[pid], active.get(pid), numbers[pid]
        rs = ratings.get(pid, [])
        current.append(
            {
                "player": ref(p),
                "role": e.role if e else "",
                "joined_on": e.joined_on if e else None,
                "on_roster": e is not None,
                "photo": _media(p.photo_cutout) or _media(p.photo),
                "cutout": bool(p.photo_cutout),
                "card": _card_ref(cards.get(pid)),
                "matches": n["matches"],
                "kills": n["kills"],
                "knocks": n["knocks"],
                "headshots": n["headshots"],
                "hs_pct": n["hs_pct"],
                "damage": damage.get(pid),
                "avg_rating": round(sum(rs) / len(rs), 1) if rs else None,
                "main_weapon": n["main_weapon"],
            }
        )
    # Most matches first, then name: the regulars lead the list.
    current.sort(key=lambda r: (-r["matches"], r["player"]["display_name"].casefold()))

    former = []
    for pid in gone_ids:
        e = ended.get(pid)
        former.append(
            {
                "player": ref(players[pid]),
                "role": e.role if e else "",
                "left_on": e.left_on if e else None,
                "matches": len(played.get(pid, [])),
            }
        )
    former.sort(key=lambda r: (r["left_on"] or date.min, r["matches"]), reverse=True)
    return {"season": season.name if season else None, "players": current, "former": former}
