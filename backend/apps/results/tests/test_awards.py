"""Weekly and monthly player awards."""

import datetime as dt

import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from apps.coach.models import WeaponName
from apps.league.models import Match, MatchDay, Player, ScoringRule, Season, Stage, Team
from apps.results.awards import period_of
from apps.results.models import MatchEvent, PlayerMatchResult
from apps.rotations.models import PlayerTrack

pytestmark = pytest.mark.django_db
K = MatchEvent.Kind
SNIPER_GUN, GRENADE, RIFLE = 21, 50, 635


@pytest.fixture(autouse=True)
def fresh_cache():
    cache.clear()


def player(n: int, name: str) -> Player:
    return Player.objects.create(
        game_uid=n, current_name_raw=name, display_name=name, search_name=name.lower()
    )


@pytest.fixture
def league():
    rule, _ = ScoringRule.objects.get_or_create(name="Test rule", defaults={"placement_points": {}})
    season = Season.objects.create(name="S1", scoring_rule=rule)
    stage = Stage.objects.create(season=season, name="Scrims")
    day = MatchDay.objects.create(stage=stage, number=1, date=dt.date(2026, 10, 6))
    alpha, bravo = Team.objects.create(name="Alpha"), Team.objects.create(name="Bravo")
    ace, rush, nade = player(1, "ACE"), player(2, "RUSH"), player(3, "NADE")
    foe1, foe2 = player(4, "FOE1"), player(5, "FOE2")
    started = dt.datetime(2026, 10, 6, 19, 0, tzinfo=dt.UTC)
    match = Match.objects.create(
        match_day=day, number=1, status=Match.Status.PUBLISHED, started_at=started
    )
    rows = [(ace, alpha, 6, 4, 2), (rush, alpha, 3, 5, 0), (nade, alpha, 2, 1, 0),
            (foe1, bravo, 1, 1, 0), (foe2, bravo, 0, 0, 0)]  # fmt: skip
    for p, team, kills, knocks, hs in rows:
        PlayerMatchResult.objects.create(
            match=match, player=p, team=team, raw_name=p.display_name,
            display_name=p.display_name, kills=kills, knocks=knocks, headshot_knocks=hs,
        )  # fmt: skip
    entity = {ace: 10, rush: 11, nade: 12, foe1: 20, foe2: 21}

    def hit(kind, t, actor, target, **kw):
        MatchEvent.objects.create(
            match=match, kind=kind, source="DEBUGGER", game_time_s=t,
            actor_entity=entity[actor], target_entity=entity[target],
            actor_player=actor, target_player=target,
            actor_team=PlayerMatchResult.objects.get(match=match, player=actor).team,
            target_team=PlayerMatchResult.objects.get(match=match, player=target).team, **kw,
        )  # fmt: skip

    # RUSH opens a fight with a knock from 8 m; ACE finishes it.
    hit(K.KNOCK, 100.0, rush, foe1)
    hit(K.KILL, 104.0, ace, foe1, weapon_id=RIFLE)
    # Much later, FOE2 opens a new fight; NADE kills him with a grenade.
    hit(K.KNOCK, 300.0, foe2, ace)
    hit(K.KILL, 305.0, nade, foe2, weapon_id=GRENADE)
    # ACE snipes FOE1 from 120 m.
    hit(K.KILL, 400.0, ace, foe1, weapon_id=SNIPER_GUN, x=0, z=0, tx=120, tz=0)
    # Tracks (decimetres every 0.5 s from 0 s): RUSH 8 m from FOE1 at 100 s.
    pts = 1000
    for p, x in [(rush, 0), (foe1, 80), (ace, 5000), (foe2, 9000), (nade, 3000)]:
        PlayerTrack.objects.create(match=match, entity_id=entity[p], player=p,
                                   start_s=0, step_s=0.5, points=[[x, 0]] * pts)  # fmt: skip
    return match


def get(params=""):
    with override_settings(PUBLIC_SITE=True):
        resp = APIClient().get(f"/api/v1/awards{params}")
    assert resp.status_code == 200, resp.content
    return {a["key"]: a for a in resp.json()["awards"]}, resp.json()


def test_periods():
    assert period_of("week", dt.date(2026, 10, 8)) == (dt.date(2026, 10, 5), dt.date(2026, 10, 11))
    assert period_of("month", dt.date(2026, 2, 14)) == (dt.date(2026, 2, 1), dt.date(2026, 2, 28))


def test_awards_for_the_latest_week(league):
    awards, data = get()
    assert data["start"] == "2026-10-05" and data["matches"] == 1
    assert data["unidentified_kills"] == 3
    top = awards["player"]["top"]
    assert [p["player"] for p in top] == ["ACE", "RUSH", "NADE"]
    assert top[0]["team"] == "Alpha" and top[0]["matches"] == [league.pk]
    rusher = awards["rusher"]["top"][0]
    assert rusher["player"] == "RUSH" and rusher["detail"] == "1 close knocks · 1 fights opened"
    # Without weapon names the weapon awards say what they need.
    assert awards["sniper"]["blocked"] and awards["sniper"]["top"] == []
    assert awards["grenader"]["blocked"]


def test_weapon_awards_once_weapons_are_named(league):
    WeaponName.objects.create(weapon_id=SNIPER_GUN, name="AWM", weapon_class="SNIPER")
    WeaponName.objects.create(weapon_id=GRENADE, name="M79", weapon_class="EXPLOSIVE")
    awards, data = get("?period=month&date=2026-10-20")
    assert (data["unidentified_kills"], data["kills"]) == (1, 3)  # the rifle isn't named
    assert awards["sniper"]["top"][0]["player"] == "ACE"
    assert awards["sniper"]["top"][0]["detail"] == "1 sniper kills · longest 120 m"
    assert awards["grenader"]["top"][0]["player"] == "NADE"


def test_drafts_and_other_weeks_do_not_count(league):
    awards, data = get("?date=2026-09-30")
    assert data["matches"] == 0 and awards["player"]["top"] == []
    Match.objects.filter(pk=league.pk).update(status=Match.Status.DRAFT)
    cache.clear()
    awards, _ = get("?date=2026-10-06")
    assert awards["player"]["top"] == []


def test_private_site_needs_sign_in(league):
    with override_settings(PUBLIC_SITE=False):
        assert APIClient().get("/api/v1/awards").status_code in (401, 403)
