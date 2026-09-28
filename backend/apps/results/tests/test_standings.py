"""Standings maths: totals, tiebreakers, shared ranks, scopes and re-scoring."""

import datetime as dt

import pytest

from apps.league.models import Group, Match, MatchDay, ScoringRule, Season, Stage, Team
from apps.results.models import StandingRow, TeamMatchResult
from apps.results.standings import rebuild_season

pytestmark = pytest.mark.django_db


@pytest.fixture
def season() -> Season:
    return Season.objects.create(
        name="Season 1", scoring_rule=ScoringRule.objects.get(name="TDL default")
    )


def teams(*names: str) -> list[Team]:
    return [Team.objects.create(name=n) for n in names]


def play(day: MatchDay, number: int, results: list[tuple[Team, int, int]], **kw) -> Match:
    """results: (team, placement, kills). Points are filled in by the rebuild."""
    match = Match.objects.create(
        match_day=day, number=number, status=kw.get("status", Match.Status.PUBLISHED)
    )
    for team, placement, kills in results:
        TeamMatchResult.objects.create(
            match=match,
            team=team,
            in_game_name=team.name,
            placement=placement,
            kills=kills,
            placement_points=0,
            kill_points=0,
            total_points=0,
        )
    return match


def table(season: Season, scope: str = "season") -> list[tuple]:
    rows = StandingRow.objects.filter(season=season, scope=scope).order_by("rank", "team__name")
    return [(r.rank, r.team.name, r.total_points) for r in rows]


def test_totals_and_tiebreakers(season):
    a, b, c = teams("Alpha", "Bravo", "Charlie")
    stage = Stage.objects.create(season=season, name="League")
    day = MatchDay.objects.create(stage=stage, number=1, date=dt.date(2026, 9, 1))
    play(day, 1, [(a, 1, 3), (b, 2, 6), (c, 3, 0)])  # A 15, B 15, C 8
    play(day, 2, [(b, 1, 0), (a, 2, 3), (c, 3, 1)])  # B 12, A 12, C 9
    rebuild_season(season)

    rows = {r.team.name: r for r in StandingRow.objects.filter(season=season, scope="season")}
    assert rows["Alpha"].total_points == rows["Bravo"].total_points == 27
    assert rows["Alpha"].booyahs == rows["Bravo"].booyahs == 1
    assert rows["Alpha"].kills == rows["Bravo"].kills == 6
    # Level on points, booyahs, kills, placement points and last match: they share 1st.
    assert table(season) == [(1, "Alpha", 27), (1, "Bravo", 27), (3, "Charlie", 17)]
    alpha = rows["Alpha"]
    assert alpha.matches_played == 2 and alpha.avg_placement == 1.5 and alpha.form == [1, 2]
    assert alpha.placement_points == 21 and alpha.kill_points == 6
    assert alpha.last_match_points == 12


def test_tiebreaker_order_is_the_seasons(season):
    a, b = teams("Alpha", "Bravo")
    stage = Stage.objects.create(season=season, name="League")
    day = MatchDay.objects.create(stage=stage, number=1)
    play(day, 1, [(a, 1, 0), (b, 2, 3)])  # A 12, B 12; A has the booyah, B the kills
    rebuild_season(season)
    assert table(season) == [(1, "Alpha", 12), (2, "Bravo", 12)]

    season.tiebreakers = ["total_points", "kills", "booyahs"]
    season.save()
    rebuild_season(season)
    assert table(season) == [(1, "Bravo", 12), (2, "Alpha", 12)]


def test_last_match_breaks_a_late_tie(season):
    a, b = teams("Alpha", "Bravo")
    season.tiebreakers = ["total_points", "last_match"]
    season.save()
    stage = Stage.objects.create(season=season, name="League")
    day2 = MatchDay.objects.create(stage=stage, number=2)  # created first on purpose
    day1 = MatchDay.objects.create(stage=stage, number=1)
    play(day2, 1, [(b, 1, 0), (a, 3, 1)])  # the latest match: B 12, A 9
    play(day1, 1, [(a, 1, 0), (b, 3, 1)])  # A 12, B 9
    rebuild_season(season)
    # 21 points each; Bravo scored more in the latest match.
    assert table(season) == [(1, "Bravo", 21), (2, "Alpha", 21)]


def test_scopes_and_groups(season):
    a, b, c, d = teams("Alpha", "Bravo", "Charlie", "Delta")
    stage = Stage.objects.create(season=season, name="Groups")
    ga = Group.objects.create(stage=stage, name="A")
    gb = Group.objects.create(stage=stage, name="B")
    ga.teams.set([a, b])
    gb.teams.set([c, d])
    day = MatchDay.objects.create(stage=stage, group=ga, number=1)
    play(day, 1, [(a, 1, 2), (b, 2, 0)])
    rebuild_season(season)

    assert table(season, f"group:{ga.pk}") == [(1, "Alpha", 14), (2, "Bravo", 9)]
    # Group B hasn't played yet: both teams listed at zero, sharing first place.
    assert table(season, f"group:{gb.pk}") == [(1, "Charlie", 0), (1, "Delta", 0)]
    assert table(season, f"day:{day.pk}") == [(1, "Alpha", 14), (2, "Bravo", 9)]
    assert table(season, f"stage:{stage.pk}") == [(1, "Alpha", 14), (2, "Bravo", 9)]
    assert table(season) == [(1, "Alpha", 14), (2, "Bravo", 9)]
    day_row = StandingRow.objects.get(scope=f"day:{day.pk}", team=a)
    assert (day_row.stage, day_row.group, day_row.match_day) == (stage, ga, day)


def test_only_published_matches_count_and_rebuild_replaces(season):
    a, b = teams("Alpha", "Bravo")
    stage = Stage.objects.create(season=season, name="League")
    day = MatchDay.objects.create(stage=stage, number=1)
    play(day, 1, [(a, 1, 0), (b, 2, 0)])
    hidden = play(day, 2, [(b, 1, 10), (a, 2, 0)], status=Match.Status.NEEDS_REVIEW)
    rebuild_season(season)
    assert table(season) == [(1, "Alpha", 12), (2, "Bravo", 9)]

    hidden.status = Match.Status.PUBLISHED
    hidden.save()
    rebuild_season(season)
    assert table(season) == [(1, "Bravo", 31), (2, "Alpha", 21)]
    assert StandingRow.objects.filter(season=season, scope="season").count() == 2


def test_rescore_uses_the_current_rule(season):
    (a,) = teams("Alpha")
    stage = Stage.objects.create(season=season, name="League")
    day = MatchDay.objects.create(stage=stage, number=1)
    play(day, 1, [(a, 12, 5)])  # 11th and below score 0 placement points
    rebuild_season(season)
    result = TeamMatchResult.objects.get(team=a)
    assert (result.placement_points, result.kill_points, result.total_points) == (0, 5, 5)

    rule = ScoringRule.objects.create(
        name="Double kills", placement_points={"12": 1}, points_per_kill=2
    )
    season.scoring_rule = rule
    season.save()
    rebuild_season(season)
    result.refresh_from_db()
    assert (result.placement_points, result.kill_points, result.total_points) == (1, 10, 11)
    assert table(season) == [(1, "Alpha", 11)]
