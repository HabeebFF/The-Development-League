"""A team's full roster on its public page: who is on it, their numbers and former players."""

import datetime as dt

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.coach.models import WeaponName
from apps.league.models import (
    Match,
    MatchDay,
    Player,
    RosterEntry,
    ScoringRule,
    Season,
    Stage,
    Team,
)
from apps.results.models import MatchEvent, PlayerCard, PlayerMatchRating, PlayerMatchResult

pytestmark = pytest.mark.django_db


def player(n, name, team=None):
    return Player.objects.create(
        game_uid=n, current_name_raw=name, display_name=name, search_name=name.lower(),
        current_team=team,
    )  # fmt: skip


@pytest.fixture
def league():
    rule, _ = ScoringRule.objects.get_or_create(name="Test rule", defaults={"placement_points": {}})
    season = Season.objects.create(name="S1", slug="s1", scoring_rule=rule, is_active=True)
    stage = Stage.objects.create(season=season)
    alpha, bravo = Team.objects.create(name="Alpha"), Team.objects.create(name="Bravo")
    ace = player(1, "ACE", alpha)
    sub = player(2, "SUB", alpha)  # never added by staff, seen in the logs
    left = player(3, "LEFT", bravo)  # played for Alpha, now plays for Bravo
    foe = player(4, "FOE", bravo)
    RosterEntry.objects.create(player=ace, team=alpha, season=season, role="IGL")
    day = MatchDay.objects.create(stage=stage, number=1, date=dt.date(2026, 10, 6))
    start = dt.datetime(2026, 10, 6, 19, tzinfo=dt.UTC)
    m1 = Match.objects.create(match_day=day, number=1, status="PUBLISHED", started_at=start)
    m2 = Match.objects.create(match_day=day, number=2, status="PUBLISHED", started_at=start)
    rows = [
        (m1, ace, alpha, 3, 4, 2, 900), (m1, left, alpha, 1, 1, 0, None),
        (m1, foe, bravo, 0, 0, 0, 0), (m2, ace, alpha, 1, 0, 0, 100),
        (m2, sub, alpha, 2, 2, 1, None), (m2, left, bravo, 4, 4, 4, None),
    ]  # fmt: skip
    for m, p, t, k, n, h, dmg in rows:
        PlayerMatchResult.objects.create(
            match=m, player=p, team=t, raw_name=p.display_name, display_name=p.display_name,
            kills=k, knocks=n, headshot_knocks=h, damage_dealt=dmg,
        )  # fmt: skip
    for m, r in ((m1, 8.0), (m2, 6.5)):
        PlayerMatchRating.objects.create(match=m, player=ace, rating=r, raw=r, stamp="x")
    WeaponName.objects.create(weapon_id=812, name="Hawk")
    for kind in (MatchEvent.Kind.KILL, MatchEvent.Kind.KNOCK):
        MatchEvent.objects.create(
            match=m1, kind=kind, source="DEBUGGER", actor_player=ace, target_player=foe,
            actor_team=alpha, target_team=bravo, weapon_id=812,
        )  # fmt: skip
    PlayerCard.objects.create(
        player=ace, week=dt.date(2026, 10, 3), team=alpha, role="RUSHER", overall=81,
        matches=2, rules="t",
    )  # fmt: skip
    PlayerCard.objects.create(  # not out yet: its week ends in the future
        player=ace, week=dt.date(2099, 1, 3), team=alpha, role="RUSHER", overall=99,
        matches=2, rules="t",
    )  # fmt: skip
    return alpha


def test_full_roster(league):
    with override_settings(PUBLIC_SITE=True):
        data = APIClient().get(f"/api/v1/teams/{league.slug}").json()
    names = [r["player"]["display_name"] for r in data["roster"]]
    assert names == ["ACE", "SUB"]  # most matches first
    ace, sub = data["roster"]
    assert ace["role"] == "IGL" and ace["on_roster"] and not sub["on_roster"]
    assert (ace["matches"], ace["kills"], ace["knocks"], ace["headshots"]) == (2, 4, 4, 2)
    assert ace["hs_pct"] == 50 and ace["damage"] == 1000 and ace["avg_rating"] == 7.2
    assert ace["main_weapon"]["name"] == "Hawk" and ace["main_weapon"]["uses"] == 2
    assert ace["card"]["overall"] == 81 and ace["card"]["tier"] == "gold"
    assert sub["card"] is None and sub["hs_pct"] == 50 and sub["damage"] is None
    # LEFT played for Alpha in match 1 only; his match for Bravo doesn't count here.
    assert [(f["player"]["display_name"], f["matches"]) for f in data["former"]] == [("LEFT", 1)]


def test_card_page_shows_shooting(league):
    ace = Player.objects.get(display_name="ACE")
    with override_settings(PUBLIC_SITE=True):
        data = APIClient().get(f"/api/v1/cards/{ace.pk}?week=2026-10-03").json()
    s = data["shooting"]
    assert (s["start"], s["end"]) == ("2026-09-12", "2026-10-09")
    assert s["hs_pct"] == 50 and s["main_weapon"]["name"] == "Hawk"
    assert s["weapons"][0] == {
        "id": 812,
        "name": "Hawk",
        "uses": 2,
        "share": 100,
        "kills": 1,
        "knocks": 1,
    }
