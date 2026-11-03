"""The match MVP banner: best rating, their weapons and abilities seen in the replay."""

import datetime as dt

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.coach.models import WeaponName
from apps.league.models import Match, MatchDay, Player, ScoringRule, Season, Stage, Team
from apps.results.models import MatchEvent, PlayerMatchRating, PlayerMatchResult
from apps.rotations.models import ReplayObject

pytestmark = pytest.mark.django_db


@pytest.fixture
def match():
    rule, _ = ScoringRule.objects.get_or_create(name="Test rule", defaults={"placement_points": {}})
    stage = Stage.objects.create(season=Season.objects.create(name="S1", scoring_rule=rule))
    day = MatchDay.objects.create(stage=stage, number=1, date=dt.date(2026, 10, 6))
    m = Match.objects.create(match_day=day, number=1, status="PUBLISHED")
    alpha, bravo = Team.objects.create(name="Alpha"), Team.objects.create(name="Bravo")
    ace, foe = (
        Player.objects.create(game_uid=n, current_name_raw=s, display_name=s, search_name=s)
        for n, s in ((1, "ACE"), (2, "FOE"))
    )
    # FOE has more kills, but ACE has the better rating.
    for p, t, kills, rating in ((ace, alpha, 3, 8.4), (foe, bravo, 5, 7.9)):
        PlayerMatchResult.objects.create(
            match=m, player=p, team=t, raw_name=p.display_name, display_name=p.display_name,
            kills=kills, knocks=4, headshot_knocks=3, damage_dealt=1500,
        )  # fmt: skip
        PlayerMatchRating.objects.create(match=m, player=p, rating=rating, raw=rating, stamp="x")
    WeaponName.objects.create(weapon_id=812, name="Hawk")
    for kind in ("KILL", "KNOCK", "KNOCK"):
        MatchEvent.objects.create(
            match=m, kind=kind, source="DEBUGGER", actor_player=ace, target_player=foe,
            actor_team=alpha, target_team=bravo, weapon_id=812,
        )  # fmt: skip
    for kind in ("BOLT_MAKER", "DINOCULARS", "DINOCULARS"):
        ReplayObject.objects.create(match=m, kind=kind, player=ace, start_s=1, end_s=2, x=0, z=0)
    ReplayObject.objects.create(
        match=m, kind="BOLT_MAKER", player=foe, start_s=1, end_s=2, x=0, z=0
    )
    return m


def get(m):
    with override_settings(PUBLIC_SITE=True):
        resp = APIClient().get(f"/api/v1/matches/{m.pk}/mvp")
    assert resp.status_code == 200, resp.content
    return resp.json()["mvp"]


def test_mvp_is_best_rating(match):
    mvp = get(match)
    assert mvp["name"] == "ACE" and mvp["rating"] == 8.4 and mvp["team"]["name"] == "Alpha"
    assert mvp["hs_pct"] == 75
    assert mvp["weapons"] == [
        {"id": 812, "name": "Hawk", "uses": 3, "share": 100, "kills": 1, "knocks": 2}
    ]
    assert mvp["skills"] == [
        {"kind": "DINOCULARS", "label": "Dinoculars", "count": 2},
        {"kind": "BOLT_MAKER", "label": "Bolt Maker", "count": 1},
    ]


def test_falls_back_to_kills_without_ratings(match):
    PlayerMatchRating.objects.all().delete()
    assert get(match)["name"] == "FOE"


def test_no_players_no_mvp(match):
    PlayerMatchResult.objects.all().delete()
    assert get(match) is None
