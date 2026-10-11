"""Task tracking: each weekly task becomes a check run on the week's matches."""

from datetime import date
from unittest import mock

from apps.coach.engine import Fight, Spot, TeamMatch, ZoneEntry
from apps.coach.models import CoachReport
from apps.coach.progress import check, goal_for, ordinal, progress, report_progress
from apps.coach.reports import changes
from apps.coach.tests.test_moments import _member, published  # noqa: F401
from apps.coach.tests.test_reports import fact


def tm(
    match, map_="bermuda", placement=5, entries=(), fights=(), deaths=(), drop=None, contested=()
):
    return TeamMatch(match, f"M{match}", map_, placement, drop, list(contested), list(entries),
                     list(fights), list(deaths), 0, 0, None)  # fmt: skip


def fight(result, zone=2, opponent=9):
    won = result == "won"
    return Fight(opponent, 100, zone, True, 2 if won else 0, 0 if won else 2, None)


LATE = fact("map:bermuda:rotation.z3.late", "Late into Zone 3", 0.75, 3, 4, [1, 2, 3, 4],
            "bermuda", zone=3)  # fmt: skip
PLACE = fact("results.placement", "Average placement 7.4", 7.4, 5, 5, [1, 2, 3, 4, 5])


def test_goal_from_a_late_rotation_fact_keeps_the_score_before():
    goal = goal_for({"facts": [LATE["id"]]}, [LATE])
    assert goal["kind"] == "late" and goal["zone"] == 3 and goal["map"] == "bermuda"
    assert goal["target"] == "Inside Zone 3 before it closes on Bermuda"
    assert goal["before"] == {"good": 1, "of": 4}


def test_goals_for_fights_deaths_drops():
    vs = fact("fights.vs9", "Lost to Bravo", 0.2, 4, 5, [1], opponent=9, opponent_name="Bravo",
              won=1, lost=4)  # fmt: skip
    die = fact(
        "deaths.top1", "Deaths at Clock Tower", 5, 3, 6, [1], place="Clock Tower", x=10, z=20
    )
    usual = fact("drops.usual", "Usual drop", 0.6, 3, 5, [1])
    contested = fact("drops.contested", "Contested", 0.5, 2, 4, [1])
    facts = [vs, die, usual, contested, PLACE]
    g = goal_for({"facts": ["fights.vs9"]}, facts)
    assert (g["kind"], g["opponent"], g["before"]) == ("vs", 9, {"good": 1, "of": 5})
    assert goal_for({"facts": ["deaths.top1"]}, facts)["before"] == {"good": 3, "of": 6}
    assert goal_for({"facts": ["drops.contested"]}, facts)["before"] == {"good": 2, "of": 4}
    drop = goal_for({"facts": ["drops.usual"]}, facts)
    assert drop["placement"] == 7 and drop["target"] == "Place 7th or better"
    assert goal_for({"facts": ["missing"]}, facts) is None
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22)] == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd"
    ]  # fmt: skip


def test_checks_skip_other_maps_and_matches_that_never_reached_the_zone():
    goal = goal_for({"facts": [LATE["id"]]}, [LATE])
    assert check(goal, tm(1, map_="kalahari", entries=[ZoneEntry(3, 20, 0.5)])) == (0, 0)
    assert check(goal, tm(1, entries=[ZoneEntry(2, 20, 0.5)])) == (0, 0)
    assert check(goal, tm(1, entries=[ZoneEntry(3, 20, 0.5)])) == (1, 1)
    assert check(goal, tm(1, entries=[ZoneEntry(3, -5, 1.2)])) == (0, 1)


def test_fight_and_death_checks():
    zf = {"kind": "zonefights", "zone": 2, "map": None}
    m = tm(1, fights=[fight("won"), fight("lost"), fight("won", zone=3)])
    assert check(zf, m) == (1, 2)
    die = {"kind": "die", "place": "Clock Tower", "x": 0, "z": 0, "map": None}
    assert check(die, tm(1, deaths=[Spot("Clock Tower", 900, 900)])) == (0, 1)
    assert check(die, tm(1, deaths=[Spot(None, 10, 10)])) == (0, 1)  # close enough
    assert check(die, tm(1, deaths=[Spot("Pochinok", 900, 900)])) == (1, 1)
    contest = {"kind": "contest", "map": None}
    assert check(contest, tm(1)) == (0, 0)  # no drop known
    assert check(contest, tm(1, drop=Spot("A", 0, 0), contested=[4])) == (0, 1)


def test_status_against_the_score_before():
    goal = goal_for({"facts": [LATE["id"]]}, [LATE])  # before: 1 of 4 on time
    on_time = [tm(i, entries=[ZoneEntry(3, 20, 0.5)]) for i in (1, 2, 3, 4)]
    late = [tm(i, entries=[ZoneEntry(3, -5, 1.2)]) for i in (5, 6)]
    assert progress(goal, [])["status"] == "untested"
    assert progress(goal, on_time[:1])["status"] == "early"
    done = progress(goal, on_time)
    assert (done["status"], done["good"], done["of"], done["matches"]) == (
        "done",
        4,
        4,
        [1, 2, 3, 4],
    )
    assert progress(goal, on_time[:1] + late[:1])["status"] == "improving"  # 50% vs 25%
    assert progress(goal, late)["status"] == "problem"


def test_report_progress_lines_up_with_tasks():
    tasks = [{"facts": [LATE["id"]]}, {"facts": ["nothing"]}]
    out = report_progress(tasks, [LATE], [tm(1, entries=[ZoneEntry(3, 20, 0.5)])])
    assert out[0]["good"] == 1 and out[1] is None


def test_monday_report_compares_last_week():
    week = [tm(4, placement=3), tm(5, placement=4)]
    before = [tm(1, placement=9), tm(2, placement=8)]
    (c,) = changes(week, before, "last week")
    assert "last week (2 matches)" in c["text"]


# -- API and schedule ----------------------------------------------------------------------


def test_reports_api_adds_this_weeks_progress(published):  # noqa: F811
    match, alpha, _ = published
    match.match_day.date = date(2026, 10, 6)
    match.match_day.save()
    facts = [fact("results.placement", "Average placement 5.0", 5.0, 3, 3, [1, 2, 3])]
    tasks = [{"title": "Drop", "why": "", "facts": ["results.placement"], "matches": []}]
    CoachReport.objects.create(team=alpha, week_start=date(2026, 10, 5), facts=facts, tasks=tasks)
    CoachReport.objects.create(team=alpha, week_start=date(2026, 9, 28), facts=facts, tasks=[])
    body = _member(alpha, "a@tdl.test").get("/api/v1/coach/teams/alpha/reports").json()
    assert [len(r["progress"]) for r in body] == [1, 0]
    assert body[0]["progress"] == [None]  # placement alone isn't a checkable task


def test_monday_task_writes_this_weeks_reports():
    from apps.coach import tasks

    with (
        mock.patch("django.utils.timezone.localdate", return_value=date(2026, 10, 7)),
        mock.patch("apps.coach.reports.write_reports", return_value=3) as write,
    ):
        assert tasks.weekly_reports_task() == 3
    write.assert_called_once_with(date(2026, 10, 5), wait=True)
