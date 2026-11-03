"""Top performers and weapons per map."""

import datetime as dt

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.coach.models import WeaponName
from apps.league.models import Match, MatchDay, Player, ScoringRule, Season, Stage, Team
from apps.maps.models import Map
from apps.results.models import MatchEvent, PlayerMatchRating, PlayerMatchResult, TeamMatchResult

pytestmark = pytest.mark.django_db


@pytest.fixture
def league():
    rule, _ = ScoringRule.objects.get_or_create(name="Test rule", defaults={"placement_points": {}})
    stage = Stage.objects.create(season=Season.objects.create(name="S1", scoring_rule=rule))
    bermuda, _ = Map.objects.get_or_create(slug="bermuda", defaults={"name": "Bermuda"})
    kalahari, _ = Map.objects.get_or_create(slug="kalahari", defaults={"name": "Kalahari"})
    alpha, bravo = Team.objects.create(name="Alpha"), Team.objects.create(name="Bravo")
    ace, foe = (
        Player.objects.create(game_uid=n, current_name_raw=s, display_name=s, search_name=s)
        for n, s in ((1, "ACE"), (2, "FOE"))
    )
    WeaponName.objects.create(weapon_id=812, name="Hawk")
    WeaponName.objects.create(weapon_id=635, name="AWM")
    day = MatchDay.objects.create(stage=stage, number=1, date=dt.date(2026, 10, 6))
    start = dt.datetime(2026, 10, 6, 19, tzinfo=dt.UTC)
    # ACE dominates Bermuda, FOE dominates Kalahari.
    for i, (mp, best, worst, weapon) in enumerate(
        [(bermuda, ace, foe, 812)] * 3 + [(kalahari, foe, ace, 635)] * 2
    ):
        m = Match.objects.create(
            match_day=day, number=i + 1, status="PUBLISHED", started_at=start, map=mp
        )
        bt, wt = (alpha, bravo) if best == ace else (bravo, alpha)
        for p, t, k, rating, place in ((best, bt, 4, 8.0, 1), (worst, wt, 1, 5.0, 2)):
            PlayerMatchResult.objects.create(
                match=m, player=p, team=t, raw_name=p.display_name, display_name=p.display_name,
                kills=k, knocks=k, headshot_knocks=1, damage_dealt=k * 500,
            )  # fmt: skip
            PlayerMatchRating.objects.create(
                match=m, player=p, rating=rating, raw=rating, stamp="x"
            )
            TeamMatchResult.objects.create(
                match=m, team=t, in_game_name=t.name, placement=place, kills=k,
                placement_points=0, kill_points=k, total_points=k,
            )  # fmt: skip
        MatchEvent.objects.create(
            match=m, kind="KILL", source="DEBUGGER", actor_player=best, target_player=worst,
            actor_team=bt, target_team=wt, weapon_id=weapon,
        )  # fmt: skip
    return {"bermuda": bermuda}


def get(params=""):
    with override_settings(PUBLIC_SITE=True):
        resp = APIClient().get(f"/api/v1/map-stats{params}")
    assert resp.status_code == 200, resp.content
    return resp.json()


def test_one_map(league):
    data = get("?map=bermuda")
    assert data["map"]["name"] == "Bermuda" and data["matches"] == 3 and data["kills"] == 15
    assert [p["player"] for p in data["fraggers"]] == ["ACE", "FOE"]
    assert data["ratings"][0]["player"] == "ACE" and data["ratings"][0]["value"] == 8.0
    assert data["damage"][0]["value"] == 2000
    assert data["weapons"] == [
        {"id": 812, "name": "Hawk", "uses": 3, "share": 100, "kills": 3, "knocks": 0}
    ]
    assert data["teams"][0]["team"]["name"] == "Alpha" and data["teams"][0]["booyahs"] == 3
    counts = {m["slug"]: m["matches"] for m in data["maps"]}
    assert counts["bermuda"] == 3 and counts["kalahari"] == 2


def test_default_map_and_minimum_matches(league):
    data = get()  # the busiest map
    assert data["map"]["slug"] == "bermuda"
    kalahari = get("?map=kalahari")
    assert kalahari["fraggers"][0]["player"] == "FOE"
    assert kalahari["ratings"] == [] and kalahari["damage"] == []  # only 2 matches each
    assert kalahari["weapons"][0]["name"] == "AWM"


def test_periods(league):
    week = get("?map=bermuda&period=week&date=2026-10-07")
    assert (week["start"], week["end"], week["matches"]) == ("2026-10-05", "2026-10-11", 3)
    assert get("?map=bermuda&period=month&date=2026-11-07")["matches"] == 0
