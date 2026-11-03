"""Top performers and most used weapons on each map, for all time, a month or a week.

For one map: the kill list (ranked like the Top player award), the best average match
ratings (at least ``MIN_MATCHES`` on the map), the most damage per match, the weapons used
most for kills and knocks, and the teams with the most Booyahs. Only published matches
count. The map of a match comes from the map number in its logs.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

from apps.league.models import Match, Team
from apps.maps.models import Map

from . import killboard, weapons
from .awards import latest_day, matches_between, period_of, published
from .models import PlayerMatchRating, PlayerMatchResult, TeamMatchResult

MIN_MATCHES = 3  # matches on the map before a player's average rating or damage counts
TOP = 10
TOP_WEAPONS = 8
PERIODS = ("all", "month", "week")


def _team(t: Team | None) -> dict | None:
    if t is None:
        return None
    return {
        "id": t.pk,
        "name": t.name,
        "tag": t.tag,
        "slug": t.slug,
        "logo": t.logo.url if t.logo else None,
        "primary_color": t.primary_color,
    }


def maps_played(matches: list[Match]) -> list[dict]:
    """Every map with how many of these matches were on it (maps with none included)."""
    count = Counter(m.map_id for m in matches)
    return [
        {"slug": mp.slug, "name": mp.name, "matches": count.get(mp.pk, 0)}
        for mp in Map.objects.filter(is_active=True).order_by("id")
    ]


def _averages(matches: list[Match]) -> tuple[list[dict], list[dict]]:
    """Best average rating and most damage per match, with ``MIN_MATCHES`` or more."""
    team_of: dict[int, Counter] = defaultdict(Counter)
    names: dict[int, str] = {}
    dmg: dict[int, list[int]] = defaultdict(list)
    for r in PlayerMatchResult.objects.filter(match__in=matches).select_related("player"):
        team_of[r.player_id][r.team_id] += 1
        names[r.player_id] = r.player.display_name
        if r.damage_dealt is not None:
            dmg[r.player_id].append(r.damage_dealt)
    ratings: dict[int, list[float]] = defaultdict(list)
    for pid, value in PlayerMatchRating.objects.filter(match__in=matches).values_list(
        "player_id", "rating"
    ):
        ratings[pid].append(value)
    teams = Team.objects.in_bulk({c.most_common(1)[0][0] for c in team_of.values()})

    def row(pid: int, value: float, n: int) -> dict:
        return {
            "player_id": pid,
            "player": names.get(pid, ""),
            "team": _team(teams.get(team_of[pid].most_common(1)[0][0])) if pid in team_of else None,
            "value": value,
            "matches": n,
        }

    rated = [
        row(pid, round(sum(rs) / len(rs), 2), len(rs))
        for pid, rs in ratings.items()
        if len(rs) >= MIN_MATCHES
    ]
    rated.sort(key=lambda r: (-r["value"], -r["matches"], r["player"].casefold()))
    damage = [
        row(pid, round(sum(ds) / len(ds)), len(ds))
        for pid, ds in dmg.items()
        if len(ds) >= MIN_MATCHES
    ]
    damage.sort(key=lambda r: (-r["value"], -r["matches"], r["player"].casefold()))
    return rated[:TOP], damage[:TOP]


def _weapons(matches: list[Match]) -> list[dict]:
    """Weapons used most for kills and knocks on this map, by everyone."""
    known = weapons.names()
    total: dict[int, dict[str, int]] = defaultdict(lambda: {"kills": 0, "knocks": 0})
    for per_player in weapons.by_weapon([m.pk for m in matches]).values():
        for wid, n in per_player.items():
            total[wid]["kills"] += n["kills"]
            total[wid]["knocks"] += n["knocks"]
    ranked = weapons.listing(
        Counter({w: n["kills"] + n["knocks"] for w, n in total.items()}), known, TOP_WEAPONS
    )
    return [{**w, **total[w["id"]]} for w in ranked]


def _teams(matches: list[Match]) -> list[dict]:
    """Teams with the most Booyahs, then the best average placement (``MIN_MATCHES``+)."""
    by: dict[int, list[int]] = defaultdict(list)
    for team_id, place in TeamMatchResult.objects.filter(match__in=matches).values_list(
        "team_id", "placement"
    ):
        by[team_id].append(place)
    teams = Team.objects.in_bulk(list(by))
    rows = [
        {
            "team": _team(teams[tid]),
            "matches": len(ps),
            "booyahs": ps.count(1),
            "avg_placement": round(sum(ps) / len(ps), 1),
        }
        for tid, ps in by.items()
        if len(ps) >= MIN_MATCHES or ps.count(1)
    ]
    rows.sort(key=lambda r: (-r["booyahs"], r["avg_placement"], r["team"]["name"].casefold()))
    return rows[:TOP]


def for_map(slug: str | None, kind: str = "all", day: date | None = None) -> dict:
    """One map's numbers. ``slug`` None picks the map with the most matches in the period."""
    if kind in ("week", "month"):
        day = day or latest_day() or date.today()
        start, end = period_of(kind, day)
        latest = latest_day()
        scope = {
            "period": kind,
            "start": start,
            "end": end,
            "previous": start - timedelta(days=1),
            "next": end + timedelta(days=1) if latest and end < latest else None,
        }
        pool = matches_between(start, end)
    else:
        scope = {"period": "all", "start": None, "end": None, "previous": None, "next": None}
        pool = list(Match.objects.filter(published()).select_related("match_day"))

    listed = maps_played(pool)
    if slug is None:
        busiest = max(listed, key=lambda m: m["matches"], default=None)
        slug = busiest["slug"] if busiest else None
    mp = Map.objects.filter(slug=slug).first() if slug else None
    matches = [m for m in pool if mp and m.map_id == mp.pk]
    board = killboard.rows(matches)
    rated, damage = _averages(matches)
    return {
        **scope,
        "maps": listed,
        "map": (
            {"slug": mp.slug, "name": mp.name, "image": mp.image.url if mp.image else None}
            if mp
            else None
        ),
        "matches": len(matches),
        "kills": sum(p["kills"] for p in board),
        "min_matches": MIN_MATCHES,
        "fraggers": board[:TOP],
        "ratings": rated,
        "damage": damage,
        "weapons": _weapons(matches),
        "teams": _teams(matches),
    }
