"""Player ratings out of 10, like football apps give after a match.

Everyone starts a match on ``base`` (5.7). Kills, knocks, headshot knocks, opening fights
and trades add to it; the team's placement and how long the player stayed alive move it up
or down; getting knocked alone and being the team's first player down take a little off.
The result is kept between ``floor`` and ``ceiling`` (3.0 and 10.0), one decimal.

A day's rating (8PM and 10PM together) or a session's is the average of the player's match
ratings in it. Player of the Day is the best average with enough matches behind it.

The numbers are the ones the player cards use (``cards.lines_for_match``), so nothing is
counted differently. Data a match doesn't have (no replay files: no trades, no "alone") just
counts as nothing; it is never a penalty.

Design: /mnt/project-files/design/PLAYER-RATINGS.md (Habeeb approved 2026-10-13).
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter, defaultdict
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, Max, Sum
from django.utils import timezone

from apps.league.models import Match, Player

from .awards import _weapon_classes, match_date, matches_between, published
from .models import (
    MatchEvent,
    PlayerMatchRating,
    PlayerMatchResult,
    RatingPoints,
    TeamMatchResult,
)

log = logging.getLogger(__name__)

RULES = "ratings-v1"

DEFAULT_POINTS = {
    # Tuned on 41 league matches (2,067 player-matches, debugger logs of 21-26 Sep 2026): a
    # normal match averages about 6.6, about 1 in 8 is 8.0 or better, 10.0 is about 1 in 170
    # (8+ kills and a Booyah).
    "base": 5.7,
    "kill": 0.18,
    "knock": 0.08,
    "headshot": 0.04,  # on top of the knock
    "opening": 0.08,
    "trade": 0.10,
    "alone_down": -0.25,
    "first_down": -0.20,
    # Time alive: out at the start is -survival, alive to the end is +survival, halfway 0.
    "survival": 0.6,
    # By the team's place: 1st (Booyah), 2nd, 3rd ... the last value covers every place after.
    "placement": [1.0, 0.7, 0.5, 0.3, 0.3, 0.1, 0.0, 0.0, -0.1, -0.2, -0.3, -0.4, -0.5],
    "floor": 3.0,
    "ceiling": 10.0,
    # Player of the Day (or Session) needs this many matches (or every match there was).
    "potd_min": 4,
}

# What staff may set, and the range each number must be in.
LIMITS = {
    "base": (0, 10),
    "kill": (0, 3),
    "knock": (0, 3),
    "headshot": (0, 3),
    "opening": (0, 3),
    "trade": (0, 3),
    "alone_down": (-3, 0),
    "first_down": (-3, 0),
    "survival": (0, 5),
    "floor": (0, 10),
    "ceiling": (0, 10),
    "potd_min": (1, 20),
}
PLACEMENT_LIMITS = (-5, 5)

LABELS = {
    "kills": "Kills",
    "knocks": "Knocks",
    "headshots": "Headshot knocks",
    "openings": "Fights opened",
    "trades": "Trades",
    "placement": "Team placement",
    "survival": "Time alive",
    "alone_downs": "Knocked while alone",
    "first_down": "First down on the team",
}


def points() -> dict:
    """The points in use: staff's, over the defaults."""
    saved = RatingPoints.objects.first()
    return {**DEFAULT_POINTS, **((saved.points if saved else None) or {})}


def place_points(place: int | None, table: list[float]) -> float:
    if not place or not table:
        return 0.0
    return table[min(place, len(table)) - 1]


def band(rating: float | None) -> str | None:
    """The colour a rating shows in, like the football apps."""
    if rating is None:
        return None
    if rating >= 9.0:
        return "gold"
    if rating >= 8.0:
        return "blue"
    if rating >= 7.0:
        return "green"
    if rating >= 6.0:
        return "orange"
    return "red"


def one_decimal(x: float) -> float:
    # Halves round up (7.25 -> 7.3), as people expect, not to the even digit.
    return float(int(x * 10 + (0.5 if x >= 0 else -0.5))) / 10


# -- One match ------------------------------------------------------------------------------


def _match_end(match: Match, alive: list[float]) -> float | None:
    """When the match ended, in game seconds: the longest anyone was tracked, the logged
    length, or the last event, whichever is latest."""
    last = MatchEvent.objects.filter(match=match).aggregate(t=Max("game_time_s"))["t"]
    found = [t for t in (*alive, match.duration_s, last) if t]
    return max(found) if found else None


def _out_times(match: Match) -> tuple[dict[int, float], dict[int, float]]:
    """From the logs alone: when each player was killed for the last time, and when each team
    was knocked out. Used when a match has no replay files."""
    deaths: dict[int, float] = {}
    for pid, t in MatchEvent.objects.filter(
        match=match, kind=MatchEvent.Kind.KILL, target_player__isnull=False,
        game_time_s__isnull=False,
    ).values_list("target_player_id", "game_time_s"):  # fmt: skip
        deaths[pid] = max(deaths.get(pid, 0.0), t)
    teams = dict(
        TeamMatchResult.objects.filter(match=match, eliminated_at_s__isnull=False).values_list(
            "team_id", "eliminated_at_s"
        )
    )
    return deaths, teams


def rate_line(line, place: int | None, alive_share: float | None, pts: dict) -> dict:
    """One player's rating for one match, and the parts it was made from."""
    parts = []

    def add(key, count, each):
        if count:
            parts.append(
                {"key": key, "label": LABELS[key], "count": count, "points": round(count * each, 2)}
            )

    add("kills", line.kills, pts["kill"])
    add("knocks", line.knocks, pts["knock"])
    add("headshots", line.headshots, pts["headshot"])
    add("openings", line.openings, pts["opening"])
    add("trades", line.trades, pts["trade"])
    if place:
        parts.append(
            {"key": "placement", "label": LABELS["placement"], "count": place,
             "points": round(place_points(place, pts["placement"]), 2)}
        )  # fmt: skip
    if alive_share is not None:
        parts.append(
            {"key": "survival", "label": LABELS["survival"], "count": round(alive_share, 2),
             "points": round((alive_share - 0.5) * 2 * pts["survival"], 2)}
        )  # fmt: skip
    add("alone_downs", line.alone_downs, pts["alone_down"])
    add("first_down", int(line.first_down), pts["first_down"])

    raw = pts["base"] + sum(p["points"] for p in parts)
    rating = one_decimal(min(max(raw, pts["floor"]), pts["ceiling"]))
    return {"rating": rating, "raw": round(raw, 2), "parts": parts}


def rate_match(match: Match, pts: dict | None = None, stamp: str = "") -> int:
    """Work out and save every player's rating in ``match``. Returns how many."""
    from .cards import _fresh_reviews, lines_for_match

    pts = pts or points()
    _fresh_reviews([match.pk])
    lines = lines_for_match(match, _weapon_classes())
    results = {
        r.player_id: r for r in PlayerMatchResult.objects.filter(match=match, player__isnull=False)
    }
    places = dict(TeamMatchResult.objects.filter(match=match).values_list("team_id", "placement"))
    alive = [ln.alive_s for ln in lines.values() if ln.alive_s]
    end = _match_end(match, alive)
    deaths, team_out = _out_times(match)

    rows = []
    for pid, r in results.items():
        line = lines.get(pid)
        if line is None:
            continue
        # The scoreboard decides kills and knocks, like everywhere else on the site.
        line.kills, line.knocks, line.headshots = r.kills, r.knocks or 0, r.headshot_knocks or 0
        out = line.alive_s
        if out is None:
            out = deaths.get(pid) or team_out.get(r.team_id) or end
        share = min(max(out / end, 0.0), 1.0) if out and end else None
        place = places.get(r.team_id)
        rated = rate_line(line, place, share, pts)
        rows.append(
            PlayerMatchRating(
                match=match, player_id=pid, team_id=r.team_id, kills=r.kills,
                knocks=r.knocks or 0, placement=place, stamp=stamp, **rated,
            )
        )  # fmt: skip
    with transaction.atomic():
        PlayerMatchRating.objects.filter(match=match).delete()
        PlayerMatchRating.objects.bulk_create(rows)
    return len(rows)


# -- Keeping them up to date ----------------------------------------------------------------


def _stamps(matches: list[Match], pts: dict) -> dict[int, str]:
    """A short fingerprint of everything a match's ratings come from: the rules, the points,
    the match itself and its scoreboard. A different fingerprint means rate it again."""
    from apps.coach import moments

    ids = [m.pk for m in matches]
    board = {
        r["match_id"]: r
        for r in PlayerMatchResult.objects.filter(match__in=ids)
        .values("match_id")
        .annotate(
            n=Count("id"), k=Sum("kills"), kn=Sum("knocks"), hs=Sum("headshot_knocks"),
            who=Sum("player_id"), teams=Sum("team_id"),
        )
    }  # fmt: skip
    placed = {
        r["match_id"]: r
        for r in TeamMatchResult.objects.filter(match__in=ids)
        .values("match_id")
        .annotate(p=Sum("placement"), t=Sum("team_id"), out=Sum("eliminated_at_s"))
    }
    head = json.dumps([RULES, moments.RULES, pts], sort_keys=True)
    out = {}
    for m in matches:
        b, p = board.get(m.pk, {}), placed.get(m.pk, {})
        text = json.dumps(
            [head, m.updated_at.isoformat(), m.duration_s, sorted(b.items()), sorted(p.items())],
            default=str,
        )
        out[m.pk] = hashlib.md5(text.encode()).hexdigest()
    return out


def refresh(matches: list[Match] | None = None, force: bool = False) -> int:
    """Rate every published match (or just ``matches``) whose ratings are missing or out of
    date, and drop ratings of matches that aren't published any more. Returns matches rated."""
    PlayerMatchRating.objects.exclude(match__status=Match.Status.PUBLISHED).delete()
    if matches is None:
        matches = list(Match.objects.filter(published()))
    else:
        matches = [m for m in matches if m.status == Match.Status.PUBLISHED]
    pts = points()
    stamps = _stamps(matches, pts)
    have = defaultdict(set)
    for mid, stamp in PlayerMatchRating.objects.filter(match__in=matches).values_list(
        "match_id", "stamp"
    ):
        have[mid].add(stamp)
    done = 0
    for m in matches:
        if not force and have.get(m.pk) == {stamps[m.pk]}:
            continue
        try:
            rate_match(m, pts, stamps[m.pk])
            done += 1
        except Exception:  # one broken match must not stop the rest
            log.exception("Ratings for match %s failed", m.pk)
    return done


# -- Days, sessions, matches and players ----------------------------------------------------


def _team(team) -> dict | None:
    if team is None:
        return None
    return {
        "id": team.pk,
        "name": team.name,
        "tag": team.tag,
        "slug": team.slug,
        "logo": team.logo.url if team.logo else None,
        "primary_color": team.primary_color,
    }


def _match_label(m: Match) -> str:
    return f"M{m.number}" + (f" · {m.map.name}" if m.map else "")


def rated_days() -> list[date]:
    """Every day with rated matches, oldest first."""
    ms = Match.objects.filter(published(), ratings__isnull=False).distinct()
    return sorted({d for m in ms.select_related("match_day") if (d := match_date(m))})


def _average(ratings: list[float]) -> float:
    return one_decimal(sum(ratings) / len(ratings))


def board(matches: list[Match], pts: dict | None = None) -> dict:
    """Every player's average rating over ``matches``, best first, and the Player of the Day
    (or Session): the best average with at least ``potd_min`` matches, or every match there
    was when fewer were played."""
    pts = pts or points()
    by_id = {m.pk: m for m in matches}
    rows = (
        PlayerMatchRating.objects.filter(match__in=list(by_id))
        .select_related("player", "team")
        .order_by("match__started_at", "match__number")
    )
    players: dict[int, dict] = {}
    teams: dict[int, Counter] = defaultdict(Counter)
    team_of = {}
    for r in rows:
        m = by_id[r.match_id]
        p = players.setdefault(
            r.player_id,
            {"player": r.player.display_name, "player_id": r.player_id, "kills": 0, "knocks": 0,
             "ratings": []},
        )  # fmt: skip
        p["kills"] += r.kills
        p["knocks"] += r.knocks
        p["ratings"].append(
            {"match": m.pk, "label": _match_label(m), "session": str(m.match_day),
             "rating": r.rating, "band": band(r.rating)}
        )  # fmt: skip
        if r.team_id:
            teams[r.player_id][r.team_id] += 1
            team_of[r.team_id] = r.team
    out = []
    for pid, p in players.items():
        values = [x["rating"] for x in p["ratings"]]
        avg = _average(values)
        common = teams[pid].most_common(1)
        out.append(
            {
                **p,
                "rating": avg,
                "band": band(avg),
                "matches": len(values),
                "best": max(values),
                "team": _team(team_of.get(common[0][0])) if common else None,
            }
        )
    out.sort(key=lambda p: (-p["rating"], -p["matches"], -p["kills"], p["player"].casefold()))
    for i, p in enumerate(out, 1):
        p["rank"] = i
    need = min(int(pts["potd_min"]), max((p["matches"] for p in out), default=0))
    star = next((p for p in out if p["matches"] >= need), None) if out else None
    if star:
        star["star"] = True
    return {
        "matches": len(matches),
        "need": need,
        "star": star["player_id"] if star else None,
        "players": out,
    }


def for_day(day: date | None, session: int | None = None) -> dict:
    """One day's ratings (``None`` is the latest day), or one session's that day."""
    days = rated_days()
    if day is None:
        day = days[-1] if days else None
    if day is None:
        return {"date": None, "previous": None, "next": None, "sessions": [], "session": None,
                **board([])}  # fmt: skip
    matches = sorted(
        matches_between(day, day), key=lambda m: (m.started_at is None, m.started_at, m.number)
    )
    sessions, seen = [], set()
    for m in matches:
        if m.match_day_id not in seen:
            seen.add(m.match_day_id)
            sessions.append({"id": m.match_day_id, "title": str(m.match_day)})
    if session is not None:
        matches = [m for m in matches if m.match_day_id == session]
    older = [d for d in days if d < day]
    newer = [d for d in days if d > day]
    return {
        "date": day,
        "previous": older[-1] if older else None,
        "next": newer[0] if newer else None,
        "sessions": sessions,
        "session": session if session in seen else None,
        **board(matches),
    }


def day_of_session(match_day) -> date | None:
    """The day a session was played (its first published match's day)."""
    first = (
        Match.objects.filter(published(), match_day=match_day)
        .select_related("match_day")
        .order_by("started_at", "number")
        .first()
    )
    return match_date(first) if first else match_day.date


def for_match(match: Match) -> dict:
    """Every player's rating in one match, best first, with how each was made."""
    rows = (
        PlayerMatchRating.objects.filter(match=match)
        .select_related("player", "team")
        .order_by("-rating", "-kills", "player__display_name")
    )
    return {
        "match": match.pk,
        "base": points()["base"],
        "players": [
            {
                "player": r.player.display_name,
                "player_id": r.player_id,
                "team": _team(r.team),
                "rating": r.rating,
                "band": band(r.rating),
                "kills": r.kills,
                "knocks": r.knocks,
                "placement": r.placement,
                "parts": r.parts,
            }
            for r in rows
        ],
    }


def for_player(player: Player, days: int = 30) -> dict:
    """A player's daily ratings (newest last, up to ``days`` of them) and their averages over
    the last 7 and 30 days."""
    rows = list(
        PlayerMatchRating.objects.filter(
            player=player, match__status=Match.Status.PUBLISHED
        ).select_related("match__match_day")
    )
    by_day: dict[date, list[float]] = defaultdict(list)
    for r in rows:
        d = match_date(r.match)
        if d:
            by_day[d].append(r.rating)
    today = timezone.localdate()

    def since(n: int) -> dict | None:
        vals = [x for d, xs in by_day.items() if d > today - timedelta(days=n) for x in xs]
        if not vals:
            return None
        avg = _average(vals)
        return {"rating": avg, "band": band(avg), "matches": len(vals)}

    daily = [
        {"date": d, "rating": _average(xs), "band": band(_average(xs)), "matches": len(xs)}
        for d, xs in sorted(by_day.items())
    ][-days:]
    return {
        "player_id": player.pk,
        "name": player.display_name,
        "days": daily,
        "week": since(7),
        "month": since(30),
        "all": {"rating": _average([r.rating for r in rows]), "matches": len(rows)}
        if rows
        else None,
    }
