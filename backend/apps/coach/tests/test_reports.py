from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Membership, Plan, StaffProfile, User
from apps.coach.engine import TeamMatch, ZoneEntry
from apps.coach.models import CoachReport
from apps.coach.reports import changes, tasks_from, week_of
from apps.league.models import Team


def fact(id_, text, value, n, of, matches, map_=None, **data):
    return {"id": id_, "topic": id_.split(":")[-1].split(".")[0], "text": text, "value": value,
            "n": n, "of": of, "matches": matches, "map": map_, "data": data}  # fmt: skip


def test_week_starts_on_monday():
    assert week_of(date(2026, 10, 3)) == date(2026, 9, 28)
    assert week_of(date(2026, 9, 28)) == date(2026, 9, 28)


def test_tasks_come_from_facts_and_cite_them():
    facts = [
        fact(
            "results.placement",
            "Average placement: 6.0 over 6 matches",
            6.0,
            6,
            6,
            [1, 2, 3, 4, 5, 6],
        ),
        fact(
            "kalahari:rotation.z3.late",
            "Got inside Zone 3 after it closed in 4 of 5 matches on Kalahari",
            0.8,
            4,
            5,
            [1, 2, 3, 4],
            "kalahari",
            zone=3,
        ),  # fmt: skip
        fact(
            "rotation.z3.late",
            "Got inside Zone 3 after it closed in 4 of 9 matches",
            0.44,
            4,
            9,
            [1, 2, 3, 4],
            zone=3,
        ),  # fmt: skip
        fact(
            "fights.vs7",
            "Against Cliq: won 1, lost 5 of 6 fights",
            0.17,
            4,
            6,
            [1, 2, 5, 6],
            opponent=7,
            opponent_name="Cliq",
            won=1,
            lost=5,
        ),  # fmt: skip
        fact(
            "fights.vs8",
            "Against Hydra: won 3, lost 3 of 6 fights",
            0.5,
            3,
            6,
            [1, 2, 3],
            opponent=8,
            opponent_name="Hydra",
            won=3,
            lost=3,
        ),  # fmt: skip
        fact(
            "deaths.top1",
            "5 player deaths at Clock Tower, in 3 of 6 matches",
            5,
            3,
            6,
            [2, 3, 4],
            place="Clock Tower",
            x=1,
            z=2,
        ),  # fmt: skip
        fact(
            "kalahari:drops.usual",
            "Usual drop on Kalahari: Refinery, in 4 of 5 matches, average placement 9.0",
            0.8,
            4,
            5,
            [1, 2, 3, 4],
            "kalahari",
            place="Refinery",
            placement=9.0,
            x=0,
            z=0,
        ),  # fmt: skip
    ]
    tasks = tasks_from(facts)
    titles = [t["title"] for t in tasks]
    # The Kalahari version of the Zone 3 problem is the stronger one, so only it is kept.
    assert "Rotate earlier into Zone 3 on Kalahari" in titles
    assert "Rotate earlier into Zone 3" not in titles
    assert "Have a plan for Cliq" in titles
    assert not any("Hydra" in t for t in titles)  # an even record isn't a problem
    assert "Stop dying at Clock Tower" in titles
    assert "Rethink your usual drop on Kalahari" in titles
    for t in tasks:
        assert t["facts"] and t["why"] and t["matches"]
    drop = next(t for t in tasks if "drop" in t["title"])
    assert drop["facts"] == ["kalahari:drops.usual", "results.placement"]


def tm(match, placement, late=False, played_on=None):
    entry = ZoneEntry(2, -10.0 if late else 60.0, 0.5)
    return TeamMatch(
        match, f"M{match}", "bermuda", placement, None, [], [entry], [], [], 0, 0, played_on
    )


def test_changes_need_two_matches_each_side_and_a_real_difference():
    earlier = [tm(1, 9, late=True), tm(2, 8, late=True), tm(3, 10)]
    assert changes([tm(4, 3)], earlier) == []
    out = changes([tm(4, 3), tm(5, 4)], earlier)
    texts = [c["text"] for c in out]
    assert texts[0].startswith("Average placement improved from 9.0 to 3.5")
    assert texts[1].startswith("Late into the zone 0% of the time, down from 67%")
    assert all(c["better"] for c in out)
    assert changes([tm(4, 9), tm(5, 9)], [tm(1, 9), tm(2, 9)]) == []


@pytest.fixture
def teams(db):
    plan = Plan.objects.get(code="league_team")
    return (Team.objects.create(name="Alpha", slug="alpha", plan=plan),
            Team.objects.create(name="Bravo", slug="bravo", plan=plan))  # fmt: skip


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def member(team, email):
    user = User.objects.create_user(email=email, password="pass-12345")
    Membership.objects.create(user=user, team=team)
    return client_for(user)


def test_each_team_sees_only_its_own_reports(teams):
    alpha, bravo = teams
    facts = [
        fact("results.placement", "Average placement: 5.0 over 3 matches", 5.0, 3, 3, [1, 2, 3])
    ]
    report = CoachReport.objects.create(team=alpha, week_start=date(2026, 9, 28), facts=facts)
    hidden = CoachReport.objects.create(
        team=alpha, week_start=date(2026, 9, 21), facts=facts, is_published=False
    )
    a, b = member(alpha, "a@tdl.test"), member(bravo, "b@tdl.test")

    assert [r["id"] for r in a.get("/api/v1/coach/teams/alpha/reports").data] == [report.pk]
    assert a.get(f"/api/v1/coach/reports/{report.pk}").status_code == 200
    assert a.get(f"/api/v1/coach/reports/{hidden.pk}").status_code == 404
    assert b.get("/api/v1/coach/teams/alpha/reports").status_code == 403
    assert b.get(f"/api/v1/coach/reports/{report.pk}").status_code == 403
    assert (
        a.patch(
            f"/api/v1/coach/reports/{report.pk}", {"is_published": False}, format="json"
        ).status_code
        == 403
    )

    Team.objects.filter(pk=alpha.pk).update(plan=None)
    fresh = client_for(User.objects.get(email="a@tdl.test"))
    assert fresh.get("/api/v1/coach/teams/alpha/reports").status_code == 403  # not in their plan


def test_staff_edit_tasks_but_must_cite_the_reports_facts(teams):
    alpha, _ = teams
    facts = [
        fact(
            "deaths.top1", "5 player deaths at Clock Tower", 5, 3, 6, [2, 3, 4], place="Clock Tower"
        )
    ]
    report = CoachReport.objects.create(team=alpha, week_start=date(2026, 9, 28), facts=facts)
    user = User.objects.create_user(email="staff@tdl.test", password="pass-12345")
    StaffProfile.objects.create(user=user, role=StaffProfile.Role.ANALYST)
    staff = client_for(user)

    url = f"/api/v1/coach/reports/{report.pk}"
    bad = staff.patch(url, {"tasks": [{"title": "Win more", "facts": ["made.up"]}]}, format="json")
    assert bad.status_code == 400
    ok = staff.patch(
        url,
        {"tasks": [{"title": "Avoid Clock Tower late", "facts": ["deaths.top1"]}]},
        format="json",
    )
    assert ok.status_code == 200, ok.data
    assert ok.data["tasks"] == [
        {
            "title": "Avoid Clock Tower late",
            "why": ["5 player deaths at Clock Tower"],
            "facts": ["deaths.top1"],
            "matches": [2, 3, 4],
        }  # fmt: skip
    ]
    assert ok.data["edited_by"] == "staff@tdl.test"
