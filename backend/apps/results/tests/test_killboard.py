"""Kill lists for a match, a session (match day), a week and a month."""

import datetime as dt

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.league.models import Match, MatchDay, Player, ScoringRule, Season, Stage, Team
from apps.results.models import PlayerMatchResult

pytestmark = pytest.mark.django_db


def player(n: int, name: str) -> Player:
    return Player.objects.create(
        game_uid=n, current_name_raw=name, display_name=name, search_name=name.lower()
    )


@pytest.fixture
def league():
    rule, _ = ScoringRule.objects.get_or_create(name="Test rule", defaults={"placement_points": {}})
    stage = Stage.objects.create(season=Season.objects.create(name="S1", scoring_rule=rule))
    alpha, bravo = Team.objects.create(name="Alpha"), Team.objects.create(name="Bravo")
    ace, two, foe = player(1, "ACE"), player(2, "TWO"), player(3, "FOE")

    def day(n, date, title):
        return MatchDay.objects.create(stage=stage, number=n, date=date, title=title)

    eight = day(1, dt.date(2026, 10, 6), "TDL DAY 1 8PM")
    ten = day(2, dt.date(2026, 10, 6), "TDL DAY 1 10PM")
    next_month = day(3, dt.date(2026, 11, 2), "TDL DAY 2 8PM")

    def match(d, n, hour, rows, status=Match.Status.PUBLISHED):
        start = dt.datetime.combine(d.date, dt.time(hour), tzinfo=dt.UTC)
        m = Match.objects.create(match_day=d, number=n, status=status, started_at=start)
        for p, team, kills, knocks, hs in rows:
            PlayerMatchResult.objects.create(
                match=m, player=p, team=team, raw_name=p.display_name,
                display_name=p.display_name, kills=kills, knocks=knocks, headshot_knocks=hs,
            )  # fmt: skip
        return m

    m1 = match(eight, 1, 19, [(ace, alpha, 4, 5, 1), (two, alpha, 2, 2, 0), (foe, bravo, 2, 3, 0)])
    match(eight, 2, 19, [(ace, alpha, 1, 1, 0), (foe, bravo, 3, 3, 2)])
    match(ten, 1, 21, [(two, alpha, 5, 5, 5), (foe, bravo, 0, 0, 0)])
    match(ten, 2, 21, [(ace, alpha, 9, 9, 9)], status=Match.Status.NEEDS_REVIEW)  # not counted
    match(next_month, 1, 19, [(foe, bravo, 7, 7, 0)])
    return {"m1": m1, "eight": eight, "ten": ten, "next_month": next_month}


def get(params):
    with override_settings(PUBLIC_SITE=True):
        resp = APIClient().get(f"/api/v1/kills{params}")
    assert resp.status_code == 200, resp.content
    return resp.json()


def table(data):
    return [(p["rank"], p["player"], p["kills"]) for p in data["players"]]


def test_one_match(league):
    data = get(f"?match={league['m1'].pk}")
    # FOE and TWO tie on kills; FOE has more knocks.
    assert table(data) == [(1, "ACE", 4), (2, "FOE", 2), (3, "TWO", 2)]
    assert data["kills"] == 8
    assert data["players"][0]["team"]["name"] == "Alpha"
    assert data["players"][0]["headshots"] == 1


def test_a_session_adds_its_matches(league):
    data = get(f"?session={league['eight'].pk}")
    assert data["session"]["title"] == "TDL DAY 1 8PM" and data["matches"] == 2
    # Same kills and knocks; FOE has more headshot knocks.
    assert table(data) == [(1, "FOE", 5), (2, "ACE", 5), (3, "TWO", 2)]
    assert data["previous"] is None and data["next"] == league["ten"].pk


def test_latest_session_skips_unpublished_matches(league):
    data = get("?session=latest")
    assert data["session"]["id"] == league["next_month"].pk
    assert data["previous"] == league["ten"].pk and data["next"] is None
    ten = get(f"?session={league['ten'].pk}")
    assert table(ten) == [(1, "TWO", 5), (2, "FOE", 0)]


def test_week_and_month(league):
    week = get("?period=week&date=2026-10-08")
    assert (week["start"], week["end"], week["matches"]) == ("2026-10-05", "2026-10-11", 3)
    assert [p["player"] for p in week["players"]] == ["TWO", "FOE", "ACE"]
    assert week["players"][0]["matches"] == 2
    assert week["next"] == "2026-10-12"
    month = get("?period=month&date=2026-11-20")
    assert table(month) == [(1, "FOE", 7)] and month["next"] is None


def test_hidden_without_public_site(league):
    with override_settings(PUBLIC_SITE=False):
        assert APIClient().get("/api/v1/kills").status_code in (401, 403)
