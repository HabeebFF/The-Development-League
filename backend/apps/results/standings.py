"""Standings: add up published match results into ranked tables.

Every season has several tables (scopes): the whole season, each stage, each group and
each match day. They are rebuilt together from scratch, so a re-upload, an edited
scoring rule or an unpublished match can never leave a stale row behind.

Points are re-scored with the season's current scoring rule on every rebuild, so
changing the rule (or switching a season to another rule) updates past matches too.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from django.db import transaction

from apps.league.models import Group, Match, Season, Team

from .models import StandingRow, TeamMatchResult

FORM_LENGTH = 5


@dataclass
class Tally:
    team_id: int
    matches_played: int = 0
    booyahs: int = 0
    kills: int = 0
    placement_points: int = 0
    kill_points: int = 0
    total_points: int = 0
    placement_sum: int = 0
    last_match_points: int | None = None
    placements: list[int] = field(default_factory=list)

    def add(self, result: TeamMatchResult) -> None:
        self.matches_played += 1
        self.booyahs += result.placement == 1
        self.kills += result.kills
        self.placement_points += result.placement_points
        self.kill_points += result.kill_points
        self.total_points += result.total_points
        self.placement_sum += result.placement
        self.last_match_points = result.total_points  # results arrive in match order
        self.placements.append(result.placement)

    def sort_value(self, tiebreaker: str) -> int:
        if tiebreaker == "last_match":
            return self.last_match_points if self.last_match_points is not None else -(10**9)
        return getattr(self, tiebreaker)


@dataclass
class Scope:
    key: str
    stage_id: int | None = None
    group_id: int | None = None
    match_day_id: int | None = None
    tallies: dict[int, Tally] = field(default_factory=dict)

    def tally(self, team_id: int) -> Tally:
        if team_id not in self.tallies:
            self.tallies[team_id] = Tally(team_id)
        return self.tallies[team_id]


def rank(tallies: list[Tally], tiebreakers: list[str], names: dict[int, str]) -> list[tuple]:
    """Sort best first. Teams level on every tiebreaker share a rank (1, 2, 2, 4)."""

    def key(t: Tally) -> tuple:
        return tuple(t.sort_value(tb) for tb in tiebreakers)

    ordered = sorted(tallies, key=lambda t: (tuple(-v for v in key(t)), names.get(t.team_id, "")))
    ranked, previous = [], None
    for position, tally in enumerate(ordered, start=1):
        if previous is None or key(tally) != previous[1]:
            previous = (position, key(tally))
        ranked.append((previous[0], tally))
    return ranked


def _match_order(match: Match) -> tuple:
    day = match.match_day
    return (day.stage.order, day.date or dt.date.max, day.number, match.number, match.pk)


def rescore(season: Season) -> int:
    """Apply the season's scoring rule to its stored results. Returns rows changed."""
    rule = season.scoring_rule
    changed = []
    for r in TeamMatchResult.objects.filter(match__match_day__stage__season=season):
        pp, kp = rule.placement_score(r.placement), rule.kill_score(r.kills)
        if (r.placement_points, r.kill_points, r.total_points) != (pp, kp, pp + kp):
            r.placement_points, r.kill_points, r.total_points = pp, kp, pp + kp
            changed.append(r)
    TeamMatchResult.objects.bulk_update(
        changed, ["placement_points", "kill_points", "total_points"]
    )
    return len(changed)


def build_scopes(season: Season) -> dict[str, Scope]:
    scopes: dict[str, Scope] = {"season": Scope("season")}

    def scope(key: str, **kw) -> Scope:
        if key not in scopes:
            scopes[key] = Scope(key, **kw)
        return scopes[key]

    # Every group gets a table, even before its first match, listing its teams at zero.
    for group in Group.objects.filter(stage__season=season).prefetch_related("teams"):
        table = scope(f"group:{group.pk}", stage_id=group.stage_id, group_id=group.pk)
        for team in group.teams.all():
            table.tally(team.pk)

    results = TeamMatchResult.objects.filter(
        match__match_day__stage__season=season, match__status=Match.Status.PUBLISHED
    ).select_related("match__match_day__stage")
    for r in sorted(results, key=lambda r: (_match_order(r.match), r.placement)):
        day = r.match.match_day
        tables = [
            scopes["season"],
            scope(f"stage:{day.stage_id}", stage_id=day.stage_id),
            scope(
                f"day:{day.pk}", stage_id=day.stage_id, group_id=day.group_id, match_day_id=day.pk
            ),
        ]
        if day.group_id:
            tables.append(
                scope(f"group:{day.group_id}", stage_id=day.stage_id, group_id=day.group_id)
            )
        for table in tables:
            table.tally(r.team_id).add(r)
    return scopes


def rebuild_season(season: Season) -> int:
    """Rebuild every standings table of a season. Returns the number of rows written."""
    season = Season.objects.select_related("scoring_rule").get(pk=season.pk)
    with transaction.atomic():
        rescore(season)
        scopes = build_scopes(season)
        team_ids = {tid for s in scopes.values() for tid in s.tallies}
        names = dict(Team.objects.filter(pk__in=team_ids).values_list("pk", "name"))
        rows = []
        for table in scopes.values():
            for position, t in rank(list(table.tallies.values()), season.tiebreakers, names):
                rows.append(
                    StandingRow(
                        season=season,
                        scope=table.key,
                        stage_id=table.stage_id,
                        group_id=table.group_id,
                        match_day_id=table.match_day_id,
                        team_id=t.team_id,
                        rank=position,
                        matches_played=t.matches_played,
                        booyahs=t.booyahs,
                        kills=t.kills,
                        placement_points=t.placement_points,
                        kill_points=t.kill_points,
                        total_points=t.total_points,
                        avg_placement=round(t.placement_sum / t.matches_played, 2)
                        if t.matches_played
                        else None,
                        last_match_points=t.last_match_points,
                        form=t.placements[-FORM_LENGTH:],
                    )
                )
        StandingRow.objects.filter(season=season).delete()
        StandingRow.objects.bulk_create(rows)
    return len(rows)


def schedule_rebuild(*season_ids: int | None) -> None:
    """Queue a rebuild for each season once the current transaction commits."""
    from .tasks import rebuild_standings_task

    for season_id in {s for s in season_ids if s}:
        transaction.on_commit(lambda sid=season_id: rebuild_standings_task.delay(sid))
