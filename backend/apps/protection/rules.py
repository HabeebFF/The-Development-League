"""Checking Protection Point tasks against the uploaded matches, and the PP table.

A task covers the published matches played on its date (or only the sessions staff picked).
Teams that didn't play any of them get no result, so they neither gain nor lose.

- ZONE_ALIVE: every player who played the match for the team is still alive when zone N
  appears (the zone counting the coach uses: the Nth stage that shrinks). Early-game deaths
  that respawned count as alive. If zone N never came, the squad must be whole at the end.
- BOOYAH: PP for each booyah (``once`` for a single reward), ``pp_not_done`` with none.
- DAY_POINTS / DAY_KILLS: the day's total (Standings points, team kills) against a number.
- PLACEMENT: top ``top`` in at least ``min_matches`` matches.
- MANUAL: nothing from the logs; staff tick each team.
"""

from __future__ import annotations

import operator
import re
from collections import defaultdict
from datetime import date

from django.db import transaction

from apps.league.models import Match, Season, Team, TeamAlias
from apps.results.awards import match_date, matches_between
from apps.results.models import MatchEvent, PlayerMatchResult, TeamMatchResult, ZonePhase

from .models import Adjustment, Period, Task, TaskResult

R = Task.Rule
OPS = {"lt": operator.lt, "lte": operator.le, "gt": operator.gt, "gte": operator.ge}
OP_WORDS = {"lt": "less than", "lte": "at most", "gt": "more than", "gte": "at least"}


# -- Matches --------------------------------------------------------------------------------


def task_matches(task: Task) -> list[Match]:
    matches = matches_between(task.date, task.date)
    sessions = set(task.match_days.values_list("pk", flat=True))
    if sessions:
        matches = [m for m in matches if m.match_day_id in sessions]
    return sorted(matches, key=lambda m: (m.match_day_id, m.number))


def zone_times(match: Match) -> list[float]:
    """When each zone (1, 2, 3...) first appeared, in game seconds."""
    shown: dict[int, float] = {}
    shrinks: set[int] = set()
    for p in ZonePhase.objects.filter(match=match, game_time_s__isnull=False).order_by(
        "game_time_s"
    ):
        if p.inner_radius > 0:
            shown.setdefault(p.stage_index, p.game_time_s)
        if p.state == ZonePhase.State.SHRINK:
            shrinks.add(p.stage_index)
    return [shown[s] for s in sorted(shrinks) if s in shown]


def final_deaths(match: Match) -> dict[int, float]:
    """Player entity -> when they died for good (a death followed by a respawn doesn't count)."""
    K = MatchEvent.Kind
    respawns: dict[int, list[float]] = defaultdict(list)
    deaths: dict[int, list[float]] = defaultdict(list)
    events = MatchEvent.objects.filter(
        match=match, kind__in=[K.DEATH, K.KILL, K.RESPAWN], game_time_s__isnull=False
    )
    for e in events:
        if e.kind == K.RESPAWN and e.actor_entity:
            respawns[e.actor_entity].append(e.game_time_s)
        elif e.kind == K.DEATH and e.actor_entity:  # the replay's death: actor is who died
            deaths[e.actor_entity].append(e.game_time_s)
        elif e.kind == K.KILL and e.target_entity:
            deaths[e.target_entity].append(e.game_time_s)
    final = {}
    for entity, times in deaths.items():
        last_respawn = max(respawns.get(entity, []), default=None)
        later = [t for t in times if last_respawn is None or t > last_respawn]
        if later:
            final[entity] = min(later)
    return final


def squad_alive(match: Match, results: list[TeamMatchResult], zone: int) -> dict[int, tuple]:
    """Team id -> (alive, note) at zone ``zone`` of ``match``."""
    times = zone_times(match)
    at = times[zone - 1] if len(times) >= zone else None
    deaths = final_deaths(match)
    squads: dict[int, list[PlayerMatchResult]] = defaultdict(list)
    for p in PlayerMatchResult.objects.filter(match=match):
        squads[p.team_id].append(p)
    out = {}
    for r in results:
        if r.eliminated_at_s is not None and (at is None or r.eliminated_at_s <= at):
            out[r.team_id] = (False, "Team out before the zone" if at else "Team out")
            continue
        dead = [
            p.display_name
            for p in squads.get(r.team_id, [])
            if p.entity_id in deaths and (at is None or deaths[p.entity_id] <= at)
        ]
        if dead and len(dead) == len(squads.get(r.team_id, [])):
            out[r.team_id] = (False, "Squad wiped before the zone" if at else "Squad wiped")
        elif dead:
            out[r.team_id] = (False, f"{', '.join(dead)} down")
        else:
            out[r.team_id] = (
                True,
                "Full squad" if at else f"Full squad at the end (no zone {zone})",
            )
    return out


# -- One task -------------------------------------------------------------------------------


def _label(m: Match) -> str:
    return f"{m.match_day} M{m.number}"


def _check(task: Task, matches: list[Match], by_team: dict[int, list[TeamMatchResult]]):
    """Team id -> (done, count, detail, evidence)."""
    p = task.params or {}
    out = {}
    if task.rule == R.ZONE_ALIVE:
        zone, need = int(p.get("zone", 5)), int(p.get("min_matches", 1))
        alive: dict[int, dict[int, tuple]] = {}
        for m in matches:
            alive[m.pk] = squad_alive(
                m, [r for rs in by_team.values() for r in rs if r.match_id == m.pk], zone
            )
        for team, rows in by_team.items():
            evidence = [
                {"match": r.match_id, "label": _label(r.match), "ok": alive[r.match_id][team][0],
                 "note": alive[r.match_id][team][1]}
                for r in rows
            ]  # fmt: skip
            n = sum(e["ok"] for e in evidence)
            out[team] = (n >= need, n, f"Alive at zone {zone} in {n} of {len(rows)}", evidence)
    elif task.rule == R.BOOYAH:
        for team, rows in by_team.items():
            wins = [r for r in rows if r.placement == 1]
            evidence = [
                {"match": r.match_id, "label": _label(r.match), "ok": True, "note": "Booyah"}
                for r in wins
            ]
            word = "booyah" if len(wins) == 1 else "booyahs"
            out[team] = (bool(wins), len(wins), f"{len(wins)} {word}", evidence)
    elif task.rule in (R.DAY_POINTS, R.DAY_KILLS):
        op, value = p.get("op", "gte"), int(p.get("value", 0))
        field, unit = (
            ("total_points", "points") if task.rule == R.DAY_POINTS else ("kills", "kills")
        )
        for team, rows in by_team.items():
            total = sum(getattr(r, field) for r in rows)
            evidence = [
                {"match": r.match_id, "label": _label(r.match), "ok": None,
                 "note": f"#{r.placement} · {getattr(r, field)} {unit}"}
                for r in rows
            ]  # fmt: skip
            out[team] = (OPS[op](total, value), total, f"{total} {unit}", evidence)
    elif task.rule == R.PLACEMENT:
        top, need = int(p.get("top", 1)), int(p.get("min_matches", 1))
        for team, rows in by_team.items():
            evidence = [
                {"match": r.match_id, "label": _label(r.match), "ok": r.placement <= top,
                 "note": f"#{r.placement}"}
                for r in rows
            ]  # fmt: skip
            n = sum(e["ok"] for e in evidence)
            out[team] = (n >= need, n, f"Top {top} in {n} of {len(rows)}", evidence)
    else:  # MANUAL
        for team in by_team:
            out[team] = (None, 0, "", [])
    return out


@transaction.atomic
def check_task(task: Task) -> int:
    """Rebuild a task's results from the matches; staff overrides and notes are kept."""
    matches = task_matches(task)
    results = TeamMatchResult.objects.filter(match__in=matches).select_related("match__match_day")
    by_team: dict[int, list[TeamMatchResult]] = defaultdict(list)
    for r in sorted(results, key=lambda r: (r.match.match_day_id, r.match.number)):
        by_team[r.team_id].append(r)
    checked = _check(task, matches, by_team)
    existing = {r.team_id: r for r in task.results.all()}
    for team, (done, count, detail, evidence) in checked.items():
        row = existing.pop(team, None) or TaskResult(task=task, team_id=team)
        row.matches = [r.match_id for r in by_team[team]]
        row.done, row.count, row.detail, row.evidence = done, count, detail, evidence
        row.task = task
        row.pp = row.score()
        row.save()
    for row in existing.values():  # no longer played that day
        if row.override is None:
            row.delete()
        else:
            row.matches, row.done, row.count, row.detail, row.evidence = (
                [],
                None,
                0,
                "Didn't play",
                [],
            )
            row.pp = row.score()
            row.save()
    return len(checked)


def refresh_season(season: Season) -> int:
    """Re-check every task on a date this season has matches (after uploads, moves, hides)."""
    dates = {
        d
        for m in Match.objects.filter(match_day__stage__season=season).select_related("match_day")
        if (d := match_date(m))
    }
    tasks = Task.objects.filter(date__in=dates) if dates else Task.objects.none()
    return sum(check_task(t) for t in tasks)


# -- The table ------------------------------------------------------------------------------


def current_period(today: date) -> Period | None:
    return (
        Period.objects.filter(starts_on__lte=today, ends_on__gte=today).first()
        or Period.objects.filter(starts_on__lte=today).first()
        or Period.objects.order_by("starts_on").first()
    )


def table(period: Period, staff: bool = False) -> list[dict]:
    """Every team in the period with its PP, best first (ties by name)."""
    rows: dict[int, dict] = {}

    def row(team_id: int) -> dict:
        return rows.setdefault(
            team_id, {"team": team_id, "pp": 0, "start": 0, "tasks": 0, "adjusted": 0}
        )

    for a in period.adjustments.all():
        r = row(a.team_id)
        r["pp"] += a.pp
        r["start" if a.kind == Adjustment.Kind.START else "adjusted"] += a.pp
    results = TaskResult.objects.filter(task__period=period)
    if not staff:
        results = results.filter(task__is_published=True)
    for res in results:
        r = row(res.team_id)
        r["pp"] += res.pp
        r["tasks"] += res.pp
    teams = Team.objects.in_bulk(list(rows))
    out = sorted(rows.values(), key=lambda r: (-r["pp"], teams[r["team"]].name.casefold()))
    for i, r in enumerate(out):
        r["rank"] = i + 1
        r["team"] = teams[r["team"]]
    return out


def task_line(task: Task) -> list[str]:
    """One task in the WhatsApp post."""
    icon = "🏆" if task.rule == R.BOOYAH else "⚠️" if task.pp_done < 0 else "🎯"
    lines = [f"{icon} {task.title.upper()}", f"→ {task.pp_done:+d} PP"]
    if task.pp_not_done:
        lines += ["", "❌ IF NOT COMPLETED", f"→ {task.pp_not_done:+d} PP"]
    return lines


def as_text(rows: list[dict], tasks: list[Task]) -> str:
    """The table (and the day's tasks) in the league's WhatsApp format."""
    groups = [
        ("🟢 POSITIVE PROTECTION POINTS", [r for r in rows if r["pp"] > 0]),
        ("⚪ ZERO PROTECTION POINTS", [r for r in rows if r["pp"] == 0]),
        ("🔴 NEGATIVE PROTECTION POINTS", [r for r in rows if r["pp"] < 0]),
    ]
    out = ["🔥 CURRENT PROTECTION POINT STANDINGS 🔥"]
    for title, group in groups:
        if not group:
            continue
        out += ["", title, ""]
        for r in group:
            pp = f"{r['pp']:+d}" if r["pp"] else "0"
            out.append(f"{r['rank']}. {r['team'].name.upper()} — {pp} PP")
    bar = "━━━━━━━━━━━━━━━━━━"
    word = lambda n: "team" if n == 1 else "teams"  # noqa: E731
    out += ["", bar, f"📊 TOTAL: {len(rows)} {word(len(rows)).upper()}"]
    kinds = zip(("🟢", "⚪", "🔴"), ("positive", "0", "negative"), groups, strict=True)
    for icon, kind, (_, g) in kinds:
        out.append(f"{icon} {len(g)} {word(len(g))} with {kind} PP")
    out.append(bar)
    if tasks:
        out += ["", "🔥 TASK FOR TODAY 🔥"]
        for t in tasks:
            out += ["", *task_line(t)]
        out += ["", "GOOD LUCK, EVERYONE! 🔥"]
    return "\n".join(out)


# -- Starting PP pasted from the old table --------------------------------------------------

LINE = re.compile(
    r"^\s*(?:\d+\s*[.)]\s*)?(?P<name>.+?)\s*[—–\-:]+\s*(?P<pp>[+\-−]?\s*\d+)\s*PP\b", re.I
)


def _key(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", name.upper())


def find_team(name: str) -> Team | None:
    key = _key(name)
    teams = list(Team.objects.all())
    exact = [t for t in teams if _key(t.name) == key or (t.tag and _key(t.tag) == key)]
    if len(exact) == 1:
        return exact[0]
    for alias in TeamAlias.objects.select_related("team"):
        if _key(alias.in_game_name) == key:
            return alias.team
    # "OUTPOST 33" for "OUTPOST-33 ESPORTS": a name that starts the same way, if only one does.
    loose = [t for t in teams if _key(t.name).startswith(key) or key.startswith(_key(t.name))]
    loose = [t for t in loose if t.is_league_member] or loose
    return loose[0] if len(loose) == 1 else None


def parse_table(text: str) -> tuple[list[tuple[Team, int, str]], list[str]]:
    """Lines like "1. BERSERK GEN — +4 PP" -> ([(team, pp, name)], [names not found])."""
    found, missing = [], []
    for line in text.splitlines():
        m = LINE.match(line)
        if not m or m["name"].upper().startswith("TOTAL"):
            continue
        name = m["name"].strip()
        pp = int(m["pp"].replace("−", "-").replace(" ", ""))
        team = find_team(name)
        if team:
            found.append((team, pp, name))
        else:
            missing.append(name)
    return found, missing


@transaction.atomic
def set_starting(period: Period, entries: list[tuple[Team, int, str]], user=None) -> int:
    period.adjustments.filter(kind=Adjustment.Kind.START).delete()
    for team, pp, _ in entries:
        Adjustment.objects.create(
            period=period, team=team, kind=Adjustment.Kind.START, pp=pp,
            reason="Starting PP", created_by=user,
        )  # fmt: skip
    return len(entries)
