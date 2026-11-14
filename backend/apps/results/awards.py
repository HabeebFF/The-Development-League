"""Player awards for a week or a month: top player, rusher, sniper and grenader.

- Top player: most kills. Ties go to more knocks, then more headshot knocks.
- Top rusher: knocks from ``CLOSE_M`` or closer plus fights they opened (the first knock or
  kill of a fight between two teams). Knock distance comes from both players' replay
  tracks, so matches uploaded without their replay files count only fights opened.
- Top sniper: kills with weapons staff class as snipers; their longest such kill is shown.
- Top grenader: kills with grenades and explosive launchers (M79, MGL140, FGL-24...).

Rusher, sniper and grenader are for players of that role only (``ROLE_ONLY``): the role
staff set on the player, else the role on their latest player card up to the end of the
period. A player with neither (too few matches for a card yet) can't win them.

Kills carry a weapon number from the logs; staff name each number once (Staff > Coach >
Weapons). Until any weapon has the class an award needs, that award says so instead of
naming a winner.

Alongside them (kept apart so the player cards' four award slots don't change):

- MVP: the best average match rating (``apps.results.ratings``), from players with at least
  ``MIN_MATCHES`` matches in the period (fewer when nobody played that many).
- Team of the week / month: most league points. Ties go to Booyahs, then kills.
- Top kill team: most team kills. Ties go to kills per match, then Booyahs.
- Best IGL: each team's manager (or staff) picks the IGL (``Team.igl``); the IGL whose team
  scored the most points per match in the matches they played, with the same minimum as the MVP.

Totals (not per match) for the team awards on purpose: they reward turning up.

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

from .models import MatchEvent, PlayerMatchResult, TeamMatchResult

CLOSE_M = 15.0
FIGHT_GAP_S = 30.0  # same as the coach: hits between two teams this close are one fight
TRACK_SLACK_S = 1.0  # a track point this close in time to the knock is good enough
TOP = 3  # winner plus runners-up
MIN_MATCHES = {"week": 4, "month": 8}  # for the MVP and Best IGL
SNIPER, THROWABLE, EXPLOSIVE = "SNIPER", "THROWABLE", "EXPLOSIVE"
GRENADER = {THROWABLE, EXPLOSIVE}
# Awards only players of one role can win (the role values of Player.CardRole).
ROLE_ONLY = {"rusher": "RUSHER", "sniper": "SNIPER", "grenader": "GRENADER"}


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
        "rule": f"Rushers only. Knocks from {CLOSE_M:g} m or closer, plus fights they opened"
        " with the first knock or kill.",
    },
    {
        "key": "sniper",
        "title": "Top sniper",
        "rule": "Snipers only. Most kills with sniper rifles.",
        "needs": {SNIPER},
    },
    {
        "key": "grenader",
        "title": "Top grenader",
        "rule": "Grenaders only. Most kills with grenades, launchers and other explosives.",
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


def roles_at(players: dict[int, Player], end: date) -> dict[int, str]:
    """Each player's role for a period ending ``end``: the one staff set on the player, else
    the role on their latest card from a week starting on or before ``end``."""
    from .models import PlayerCard

    roles: dict[int, str] = {}
    cards = PlayerCard.objects.filter(player_id__in=list(players), week__lte=end).order_by(
        "player_id", "-week"
    )
    for pid, role in cards.values_list("player_id", "role"):
        roles.setdefault(pid, role)
    roles.update({pid: p.card_role for pid, p in players.items() if p.card_role})
    return roles


def awards(kind: str, day: date, between: tuple[date, date] | None = None) -> dict:
    """``between`` overrides the period (the player cards' Saturday to Friday week)."""
    start, end = between or period_of(kind, day)
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
    roles = roles_at(players, end)

    def person(pid: int, key: str) -> dict:
        t = totals[pid]
        team = teams.get(t.teams.most_common(1)[0][0]) if t.teams else None
        value, detail = _numbers(key, t.line)
        return {
            "player": players[pid].display_name if pid in players else "Unknown player",
            "player_id": pid,
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
            role = ROLE_ONLY.get(a["key"])
            ranked = sorted(
                (
                    pid
                    for pid in totals
                    if _score(a["key"], totals[pid].line)[0] > 0
                    and (role is None or roles.get(pid) == role)
                ),
                key=lambda pid: _score(a["key"], totals[pid].line),
                reverse=True,
            )
            entry["top"] = [person(pid, a["key"]) for pid in ranked[:TOP]]
        out.append(entry)

    from apps.coach.models import WeaponName

    team_out = team_awards(kind, matches)
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
        "mvp": mvp(kind, matches),
        "team_awards": team_out,
        # Kills whose weapon staff haven't named: they can't count for sniper or grenader.
        "unidentified_kills": unknown,
        "kills": kills.count(),
    }


# -- MVP and team awards --------------------------------------------------------------------


def _team_fields(team: Team | None) -> dict:
    return {
        "team": team.name if team else None,
        "team_slug": team.slug if team else None,
        "team_tag": team.tag if team else "",
        "team_color": team.primary_color if team else "",
        "logo": team.logo.url if team and team.logo else None,
    }


def _plural(n: int | float, word: str) -> str:
    return f"{n:g} {word}{'' if n == 1 else 'es' if word.endswith('ch') else 's'}"


def mvp(kind: str, matches: list[Match]) -> dict:
    """The best average match rating, from players who played enough of the period."""
    from .ratings import board, points

    entry = {
        "key": "mvp",
        "title": f"MVP of the {kind}",
        "rule": f"Best average player rating, from players with at least {MIN_MATCHES[kind]}"
        " matches (or the most anyone played). Ties go to more matches, then more kills.",
        "top": [],
    }
    pts = {**points(), "potd_min": MIN_MATCHES[kind]}
    table = board(matches, pts)
    need = table["need"]
    picked = [p for p in table["players"] if p["matches"] >= need][:TOP]
    teams = {t.pk: t for t in Team.objects.filter(pk__in=[p["team"]["id"] for p in picked
                                                         if p["team"]])}  # fmt: skip
    for p in picked:
        entry["top"].append(
            {
                "player": p["player"],
                "player_id": p["player_id"],
                **_team_fields(teams.get(p["team"]["id"]) if p["team"] else None),
                "value": p["rating"],
                "detail": f"{p['rating']:.1f} average · {_plural(p['matches'], 'match')}"
                f" · {_plural(p['kills'], 'kill')}",
                "matches": sorted({r["match"] for r in p["ratings"]}),
            }
        )
    return entry


@dataclass
class TeamLine:
    points: int = 0
    kills: int = 0
    booyahs: int = 0
    placements: list[int] = field(default_factory=list)
    matches: list[int] = field(default_factory=list)

    def add(self, r: TeamMatchResult) -> None:
        self.points += r.total_points
        self.kills += r.kills
        self.booyahs += r.placement == 1
        self.placements.append(r.placement)
        self.matches.append(r.match_id)

    @property
    def played(self) -> int:
        return len(self.matches)

    @property
    def avg_place(self) -> float:
        return sum(self.placements) / len(self.placements) if self.placements else 99.0


def team_awards(kind: str, matches: list[Match]) -> list[dict]:
    """Team of the week (or month), Top kill team and Best IGL."""
    results = list(
        TeamMatchResult.objects.filter(match__in=matches).select_related("team", "team__igl")
    )
    lines: dict[int, TeamLine] = defaultdict(TeamLine)
    by_match: dict[tuple[int, int], TeamMatchResult] = {}
    teams: dict[int, Team] = {}
    for r in results:
        lines[r.team_id].add(r)
        by_match[(r.match_id, r.team_id)] = r
        teams[r.team_id] = r.team

    def team_row(tid: int, value, detail: str, line: TeamLine) -> dict:
        return {
            "player": None,
            "player_id": None,
            **_team_fields(teams[tid]),
            "value": value,
            "detail": detail,
            "matches": sorted(set(line.matches)),
        }

    def summary(ln: TeamLine) -> str:
        return (
            f"{_plural(ln.points, 'point')} · {_plural(ln.played, 'match')}"
            f" · {_plural(ln.booyahs, 'Booyah')} · average place {ln.avg_place:.1f}"
        )

    best = sorted(
        (t for t in lines if lines[t].played),
        key=lambda t: (lines[t].points, lines[t].booyahs, lines[t].kills),
        reverse=True,
    )[:TOP]
    killers = sorted(
        (t for t in lines if lines[t].kills > 0),
        key=lambda t: (lines[t].kills, lines[t].kills / lines[t].played, lines[t].booyahs),
        reverse=True,
    )[:TOP]
    out = [
        {
            "key": "team",
            "title": f"Team of the {kind}",
            "rule": "Most league points (placement plus kill points). Ties go to more Booyahs,"
            " then more kills.",
            "top": [team_row(t, lines[t].points, summary(lines[t]), lines[t]) for t in best],
        },
        {
            "key": "kill_team",
            "title": "Top kill team",
            "rule": "Most team kills. Ties go to more kills per match, then more Booyahs.",
            "top": [
                team_row(
                    t,
                    lines[t].kills,
                    f"{_plural(lines[t].kills, 'kill')} · {_plural(lines[t].played, 'match')}"
                    f" · {lines[t].kills / lines[t].played:.1f} per match",
                    lines[t],
                )
                for t in killers
            ],
        },
    ]

    # Best IGL: the team's results in the matches its IGL played for it.
    igl_entry = {
        "key": "igl",
        "title": "Best IGL",
        "rule": "Each team manager picks their IGL in the Team area. The IGL whose team scored"
        " the most points per match in the matches they played, with at least"
        f" {MIN_MATCHES[kind]} matches (or the most any IGL played). Ties go to better"
        " average placement, then more matches.",
        "top": [],
    }
    igls = {tid: t.igl for tid, t in teams.items() if t.igl_id}
    played = PlayerMatchResult.objects.filter(
        match__in=matches, player_id__in=[p.pk for p in igls.values()]
    ).values_list("match_id", "player_id", "team_id")
    igl_lines: dict[int, TeamLine] = defaultdict(TeamLine)
    for match_id, player_id, team_id in played:
        igl = igls.get(team_id)
        if igl and igl.pk == player_id and (r := by_match.get((match_id, team_id))):
            igl_lines[team_id].add(r)
    total_igls = Team.objects.filter(igl__isnull=False, is_league_member=True).count()
    igl_entry["teams_with_igl"] = total_igls
    if not total_igls:
        igl_entry["blocked"] = (
            "No team has picked its IGL yet. Team managers pick theirs in the Team area."
        )
    elif igl_lines:
        need = min(MIN_MATCHES[kind], max(ln.played for ln in igl_lines.values()))
        ranked = sorted(
            (t for t, ln in igl_lines.items() if ln.played >= need),
            key=lambda t: (
                igl_lines[t].points / igl_lines[t].played,
                -igl_lines[t].avg_place,
                igl_lines[t].played,
            ),
            reverse=True,
        )[:TOP]
        for t in ranked:
            ln = igl_lines[t]
            per = round(ln.points / ln.played, 1)
            igl_entry["top"].append(
                {
                    **team_row(t, per, "", ln),
                    "player": igls[t].display_name,
                    "player_id": igls[t].pk,
                    "detail": f"{per:g} points per match · {_plural(ln.played, 'match')}"
                    f" · average place {ln.avg_place:.1f}",
                }
            )
    out.append(igl_entry)
    return out


def periods_played() -> list[tuple[str, date]]:
    """Every week and month with published matches, newest first, as (kind, first day)."""
    days = set()
    for m in Match.objects.filter(published()).select_related("match_day"):
        if d := match_date(m):
            days.add(d)
    seen = {(k, period_of(k, d)[0]) for d in days for k in ("week", "month")}
    return sorted(seen, key=lambda p: (p[1], p[0]), reverse=True)


def team_trophies(team: Team) -> list[dict]:
    """Every team award (and Best IGL) this team has won, newest first."""
    stamp = (
        Match.objects.filter(published()).aggregate(u=Max("updated_at"))["u"],
        Team.objects.aggregate(u=Max("updated_at"))["u"],
    )
    key = "awards:trophies:" + hashlib.md5(repr(stamp).encode()).hexdigest()
    table = cache.get(key)
    if table is None:
        table = []
        for kind, start in periods_played():
            start, end = period_of(kind, start)
            for a in team_awards(kind, matches_between(start, end)):
                if a["top"]:
                    w = a["top"][0]
                    table.append(
                        {"kind": kind, "start": start, "end": end, "key": a["key"],
                         "title": a["title"], "team_slug": w["team_slug"],
                         "player": w["player"], "detail": w["detail"]}
                    )  # fmt: skip
        cache.set(key, table, 60 * 60 * 24)
    return [{k: v for k, v in t.items() if k != "team_slug"} for t in table
            if t["team_slug"] == team.slug]  # fmt: skip
