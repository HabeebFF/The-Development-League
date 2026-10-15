"""Kill lists: every player's kills in one match, one session (match day), a week or a month.

Ranked like the Top player award: most kills, ties go to more knocks, then more headshot
knocks. Numbers come from the scoreboard (``PlayerMatchResult``), so self-kills and teammate
deaths never count. Only published matches count; weeks run Monday to Sunday.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

from django.db.models import Min

from apps.league.models import Match, MatchDay, Team

from .awards import latest_day, matches_between, period_of, published
from .models import PlayerMatchResult


def rows(matches: list[Match]) -> list[dict]:
    """One row per player who played in ``matches``, best first."""
    totals: dict[int, dict] = {}
    teams: dict[int, Counter] = defaultdict(Counter)
    played: dict[int, set] = defaultdict(set)
    results = PlayerMatchResult.objects.filter(match__in=matches).select_related("player")
    for r in results:
        t = totals.setdefault(
            r.player_id,
            {"player": r.player.display_name, "player_id": r.player_id,
             "kills": 0, "knocks": 0, "headshots": 0, "damage": None},
        )  # fmt: skip
        t["kills"] += r.kills
        t["knocks"] += r.knocks or 0
        t["headshots"] += r.headshot_knocks or 0
        if r.damage_dealt is not None:  # None: no replay .bin, so damage is unknown
            t["damage"] = (t["damage"] or 0) + r.damage_dealt
        teams[r.player_id][r.team_id] += 1
        played[r.player_id].add(r.match_id)

    team_of = {pid: c.most_common(1)[0][0] for pid, c in teams.items()}
    by_id = {t.pk: t for t in Team.objects.filter(pk__in=set(team_of.values()))}
    key = lambda t: (t["kills"], t["knocks"], t["headshots"])  # noqa: E731
    ranked = sorted(totals.values(), key=lambda t: (*(-v for v in key(t)), t["player"].lower()))
    out, rank, last = [], 0, None
    for i, t in enumerate(ranked, 1):
        if key(t) != last:
            rank, last = i, key(t)
        team = by_id.get(team_of.get(t["player_id"]))
        out.append(
            {
                **t,
                "rank": rank,
                "matches": len(played[t["player_id"]]),
                "team": (
                    {
                        "id": team.pk,
                        "name": team.name,
                        "tag": team.tag,
                        "slug": team.slug,
                        "logo": team.logo.url if team.logo else None,
                        "primary_color": team.primary_color,
                    }
                    if team
                    else None
                ),
            }
        )
    return out


def _board(scope: dict, matches: list[Match]) -> dict:
    players = rows(matches)
    return {
        **scope,
        "matches": len(matches),
        "kills": sum(p["kills"] for p in players),
        "players": players,
    }


def for_match(match: Match) -> dict:
    return _board({"scope": "match", "match": match.pk}, [match])


def _sessions() -> list[MatchDay]:
    """Match days with published matches, oldest first (by their first match)."""
    days = (
        MatchDay.objects.filter(matches__status=Match.Status.PUBLISHED)
        .annotate(first=Min("matches__started_at"))
        .distinct()
    )

    def order(d):
        return (d.date or date.min, d.first is None, d.first, d.number, d.pk)

    return sorted(days, key=order)


def for_session(day: MatchDay | None) -> dict:
    """One match day; ``None`` is the latest one."""
    days = _sessions()
    if day is None:
        day = days[-1] if days else None
    if day is None:
        return _board({"scope": "session", "session": None, "previous": None, "next": None}, [])
    ids = [d.pk for d in days]
    i = ids.index(day.pk) if day.pk in ids else None
    matches = list(
        Match.objects.filter(published(), match_day=day).order_by("started_at", "number")
    )
    return _board(
        {
            "scope": "session",
            "session": {"id": day.pk, "title": str(day), "date": day.date},
            "previous": ids[i - 1] if i else None,
            "next": ids[i + 1] if i is not None and i + 1 < len(ids) else None,
        },
        matches,
    )


def for_period(kind: str, day: date) -> dict:
    start, end = period_of(kind, day)
    latest = latest_day()
    return _board(
        {
            "scope": kind,
            "start": start,
            "end": end,
            "previous": start - timedelta(days=1),
            "next": end + timedelta(days=1) if latest and end < latest else None,
        },
        matches_between(start, end),
    )
