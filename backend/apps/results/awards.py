"""Player awards for a week or a month: top player, rusher, sniper and grenader.

- Top player: most kills. Ties go to more knocks, then more headshot knocks.
- Top rusher: knocks from ``CLOSE_M`` or closer plus fights they opened (the first knock or
  kill of a fight between two teams). Knock distance comes from both players' replay
  tracks, so matches uploaded without their replay files count only fights opened.
- Top sniper: kills with weapons staff class as snipers; their longest such kill is shown.
- Top grenader: kills with grenades and explosive launchers (M79, MGL140, FGL-24...).

Kills carry a weapon number from the logs; staff name each number once (Staff > Coach >
Weapons). Until any weapon has the class an award needs, that award says so instead of
naming a winner.

A week runs Monday to Sunday; a month is a calendar month. Only published matches count,
dated by when they started (or their match day when the start is unknown).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.core.cache import cache
from django.db.models import Max, Q
from django.utils import timezone

from apps.league.models import Match, Player, Team

from .models import MatchEvent, PlayerMatchResult

CLOSE_M = 15.0
FIGHT_GAP_S = 30.0  # same as the coach: hits between two teams this close are one fight
TRACK_SLACK_S = 1.0  # a track point this close in time to the knock is good enough
TOP = 3  # winner plus runners-up
SNIPER, THROWABLE, EXPLOSIVE = "SNIPER", "THROWABLE", "EXPLOSIVE"
GRENADER = {THROWABLE, EXPLOSIVE}


@dataclass
class Line:
    """One player's numbers in one match."""

    team: int | None = None
    kills: int = 0
    knocks: int = 0
    headshots: int = 0
    close_knocks: int = 0
    openings: int = 0
    sniper_kills: int = 0
    longest_snipe: float = 0.0
    throwable_kills: int = 0

    def add(self, other: Line) -> None:
        for k in ("kills", "knocks", "headshots", "close_knocks", "openings"):
            setattr(self, k, getattr(self, k) + getattr(other, k))
        self.sniper_kills += other.sniper_kills
        self.throwable_kills += other.throwable_kills
        self.longest_snipe = max(self.longest_snipe, other.longest_snipe)


@dataclass
class Total:
    line: Line = field(default_factory=Line)
    matches: list[int] = field(default_factory=list)
    teams: Counter = field(default_factory=Counter)


# -- Periods --------------------------------------------------------------------------------


def period_of(kind: str, day: date) -> tuple[date, date]:
    """First and last day of the week or month containing ``day``."""
    if kind == "month":
        start = day.replace(day=1)
        nxt = (start + timedelta(days=32)).replace(day=1)
        return start, nxt - timedelta(days=1)
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def match_date(m: Match) -> date | None:
    return timezone.localtime(m.started_at).date() if m.started_at else m.match_day.date


def published() -> Q:
    return Q(status=Match.Status.PUBLISHED)


def matches_between(start: date, end: date) -> list[Match]:
    qs = (
        Match.objects.filter(published())
        .filter(
            Q(
                started_at__date__gte=start - timedelta(days=1),
                started_at__date__lte=end + timedelta(days=1),
            )
            | Q(started_at__isnull=True, match_day__date__gte=start, match_day__date__lte=end)
        )
        .select_related("match_day")
    )
    return [m for m in qs if (d := match_date(m)) and start <= d <= end]


def latest_day() -> date | None:
    m = Match.objects.filter(published()).select_related("match_day")
    newest = m.order_by("-started_at").exclude(started_at=None).first()
    by_day = m.aggregate(d=Max("match_day__date"))["d"]
    days = [d for d in (newest and match_date(newest), by_day) if d]
    return max(days) if days else None


# -- One match ------------------------------------------------------------------------------


def _weapon_classes() -> dict[int, str]:
    from apps.coach.models import WeaponName

    return {w.weapon_id: w.weapon_class for w in WeaponName.objects.exclude(weapon_class="")}


def _track_points(match: Match, entities: set[int]) -> dict[int, tuple[float, float, list]]:
    from apps.rotations.models import PlayerTrack

    rows = PlayerTrack.objects.filter(match=match, entity_id__in=entities)
    return {r.entity_id: (r.start_s, r.step_s, r.points) for r in rows}


def _position(track, t: float) -> tuple[float, float] | None:
    """Where a player was at ``t`` in metres, from their track, if it covers that moment."""
    if track is None:
        return None
    start, step, points = track
    i = round((t - start) / step)
    if not 0 <= i < len(points) or abs(start + i * step - t) > TRACK_SLACK_S or not points[i]:
        return None
    return points[i][0] / 10, points[i][1] / 10


def match_lines(match: Match, classes: dict[int, str]) -> dict[int, Line]:
    """Every player's numbers in ``match``, keyed by player id."""
    lines: dict[int, Line] = defaultdict(Line)
    for r in PlayerMatchResult.objects.filter(match=match):
        line = lines[r.player_id]
        line.team = r.team_id
        line.kills = r.kills
        line.knocks = r.knocks or 0
        line.headshots = r.headshot_knocks or 0

    events = list(
        MatchEvent.objects.filter(
            match=match, kind__in=[MatchEvent.Kind.KILL, MatchEvent.Kind.KNOCK]
        ).order_by("game_time_s", "id")
    )
    knocks = [e for e in events if e.kind == MatchEvent.Kind.KNOCK and e.game_time_s is not None]
    tracks = _track_points(
        match, {e for k in knocks for e in (k.actor_entity, k.target_entity) if e is not None}
    )
    for k in knocks:
        if k.actor_player_id is None:
            continue
        a = _position(tracks.get(k.actor_entity), k.game_time_s)
        b = _position(tracks.get(k.target_entity), k.game_time_s)
        if a and b and math.dist(a, b) <= CLOSE_M:
            lines[k.actor_player_id].close_knocks += 1

    for e in events:
        if e.kind != MatchEvent.Kind.KILL or e.actor_player_id is None:
            continue
        kind = classes.get(e.weapon_id)
        if kind == SNIPER:
            line = lines[e.actor_player_id]
            line.sniper_kills += 1
            if None not in (e.x, e.z, e.tx, e.tz):
                line.longest_snipe = max(line.longest_snipe, math.dist((e.x, e.z), (e.tx, e.tz)))
        elif kind in GRENADER:
            lines[e.actor_player_id].throwable_kills += 1

    # Fights between two teams: whoever lands the first hit opened it.
    last_hit: dict[frozenset, float] = {}
    for e in events:
        if (
            e.game_time_s is None
            or None in (e.actor_team_id, e.target_team_id)
            or e.actor_team_id == e.target_team_id
        ):
            continue
        pair = frozenset((e.actor_team_id, e.target_team_id))
        before = last_hit.get(pair)
        if (before is None or e.game_time_s - before > FIGHT_GAP_S) and e.actor_player_id:
            lines[e.actor_player_id].openings += 1
        last_hit[pair] = e.game_time_s
    return dict(lines)


def _cached_lines(match: Match, classes: dict[int, str], version: str) -> dict[int, Line]:
    key = f"awards:{match.pk}:{match.updated_at.timestamp()}:{version}"
    lines = cache.get(key)
    if lines is None:
        lines = match_lines(match, classes)
        cache.set(key, lines, 60 * 60 * 24)
    return lines


# -- Awards ---------------------------------------------------------------------------------

AWARDS = [
    {
        "key": "player",
        "title": "Top player",
        "rule": "Most kills. Ties go to more knocks, then more headshot knocks.",
    },
    {
        "key": "rusher",
        "title": "Top rusher",
        "rule": f"Knocks from {CLOSE_M:g} m or closer, plus fights they opened with the first"
        " knock or kill.",
    },
    {
        "key": "sniper",
        "title": "Top sniper",
        "rule": "Most kills with sniper rifles.",
        "needs": {SNIPER},
    },
    {
        "key": "grenader",
        "title": "Top grenader",
        "rule": "Most kills with grenades, launchers and other explosives.",
        "needs": GRENADER,
    },
]


def _score(key: str, ln: Line) -> tuple:
    if key == "player":
        return (ln.kills, ln.knocks, ln.headshots)
    if key == "rusher":
        return (ln.close_knocks + ln.openings, ln.close_knocks, ln.kills)
    if key == "sniper":
        return (ln.sniper_kills, ln.longest_snipe)
    return (ln.throwable_kills, ln.kills)


def _numbers(key: str, ln: Line) -> tuple[int, str]:
    """The headline number and the line under it."""
    if key == "player":
        return ln.kills, f"{ln.kills} kills · {ln.knocks} knocks · {ln.headshots} headshot knocks"
    if key == "rusher":
        score = ln.close_knocks + ln.openings
        return score, f"{ln.close_knocks} close knocks · {ln.openings} fights opened"
    if key == "sniper":
        longest = f" · longest {ln.longest_snipe:.0f} m" if ln.longest_snipe else ""
        return ln.sniper_kills, f"{ln.sniper_kills} sniper kills{longest}"
    return ln.throwable_kills, f"{ln.throwable_kills} explosive kills"


def awards(kind: str, day: date) -> dict:
    start, end = period_of(kind, day)
    matches = matches_between(start, end)
    classes = _weapon_classes()
    version = hashlib.md5(json.dumps(sorted(classes.items())).encode()).hexdigest()[:10]
    totals: dict[int, Total] = defaultdict(Total)
    for m in matches:
        for player_id, ln in _cached_lines(m, classes, version).items():
            t = totals[player_id]
            t.line.add(ln)
            t.matches.append(m.pk)
            if ln.team:
                t.teams[ln.team] += 1

    ids = [pid for pid in totals]
    players = {p.pk: p for p in Player.objects.filter(pk__in=ids)}
    team_ids = {t.teams.most_common(1)[0][0] for t in totals.values() if t.teams}
    teams = {t.pk: t for t in Team.objects.filter(pk__in=team_ids)}

    def person(pid: int, key: str) -> dict:
        t = totals[pid]
        team = teams.get(t.teams.most_common(1)[0][0]) if t.teams else None
        value, detail = _numbers(key, t.line)
        return {
            "player": players[pid].display_name if pid in players else "Unknown player",
            "team": team.name if team else None,
            "team_slug": team.slug if team else None,
            "team_tag": team.tag if team else "",
            "team_color": team.primary_color if team else "",
            "logo": team.logo.url if team and team.logo else None,
            "value": value,
            "detail": detail,
            "matches": sorted(set(t.matches)),
        }

    out = []
    have = set(classes.values())
    for a in AWARDS:
        needs = a.get("needs")
        entry = {"key": a["key"], "title": a["title"], "rule": a["rule"], "top": []}
        if needs and not needs & have:
            entry["blocked"] = "Needs weapon names: staff haven't marked which weapons count yet."
        else:
            ranked = sorted(
                (pid for pid in totals if _score(a["key"], totals[pid].line)[0] > 0),
                key=lambda pid: _score(a["key"], totals[pid].line),
                reverse=True,
            )
            entry["top"] = [person(pid, a["key"]) for pid in ranked[:TOP]]
        out.append(entry)

    from apps.coach.models import WeaponName

    named = set(WeaponName.objects.values_list("weapon_id", flat=True))
    kills = MatchEvent.objects.filter(match__in=matches, kind=MatchEvent.Kind.KILL)
    unknown = kills.exclude(weapon_id__in=named).count()
    latest = latest_day()
    return {
        "period": kind,
        "start": start,
        "end": end,
        "matches": len(matches),
        "previous": start - timedelta(days=1),
        "next": end + timedelta(days=1) if latest and end < latest else None,
        "awards": out,
        # Kills whose weapon staff haven't named: they can't count for sniper or grenader.
        "unidentified_kills": unknown,
        "kills": kills.count(),
    }
