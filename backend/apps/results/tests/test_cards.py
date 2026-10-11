"""FUT style player cards: ratings, roles, weekly changes and the API."""

import datetime as dt
import io

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.coach.models import WeaponName
from apps.league.models import Match, MatchDay, Player, ScoringRule, Season, Stage, Team
from apps.results import cards
from apps.results.models import (
    CardWeights,
    MatchEvent,
    PlayerCard,
    PlayerMatchResult,
    TeamMatchResult,
)
from apps.rotations.models import PlayerTrack

pytestmark = pytest.mark.django_db
K = MatchEvent.Kind
SNIPER_GUN, GRENADE, RIFLE = 21, 50, 635
WEEK_A, WEEK_B = dt.date(2026, 10, 5), dt.date(2026, 10, 12)


@pytest.fixture(autouse=True)
def fresh_cache():
    cache.clear()


def player(n: int, name: str) -> Player:
    return Player.objects.create(
        game_uid=n, current_name_raw=name, display_name=name, search_name=name.lower()
    )


class League:
    def __init__(self):
        rule, _ = ScoringRule.objects.get_or_create(name="Test", defaults={"placement_points": {}})
        self.stage = Stage.objects.create(
            season=Season.objects.create(name="S1", scoring_rule=rule)
        )
        self.alpha, self.bravo = (
            Team.objects.create(name="Alpha"),
            Team.objects.create(name="Bravo"),
        )
        names = ["RUSH", "SNIPE", "NADE", "ACE", "FOE1", "FOE2", "FOE3", "FOE4"]
        self.p = {n: player(i + 1, n) for i, n in enumerate(names)}
        self.entity = {n: 10 + i for i, n in enumerate(names)}
        self.n = 0
        WeaponName.objects.create(weapon_id=SNIPER_GUN, name="AWM", weapon_class="SNIPER")
        WeaponName.objects.create(weapon_id=GRENADE, name="Grenade", weapon_class="THROWABLE")
        WeaponName.objects.create(weapon_id=RIFLE, name="AK", weapon_class="AR")

    def team(self, name):
        return self.alpha if name in ("RUSH", "SNIPE", "NADE", "ACE") else self.bravo

    def match(self, day: dt.date, blank_weapons=False, who=None):
        """One match, one fight: RUSH opens it from 8 m, SNIPE snipes twice (once with no
        weapon logged, from 130 m), NADE gets two grenade kills, FOE4 knocks ACE."""
        self.n += 1
        md = MatchDay.objects.create(stage=self.stage, number=self.n, date=day)
        start = dt.datetime.combine(day, dt.time(19), tzinfo=dt.UTC)
        m = Match.objects.create(
            match_day=md, number=1, status=Match.Status.PUBLISHED, started_at=start
        )
        for place, team in enumerate((self.alpha, self.bravo), 1):
            TeamMatchResult.objects.create(
                match=m, team=team, in_game_name=team.name, placement=place, kills=0,
                placement_points=0, kill_points=0, total_points=0,
            )  # fmt: skip
        stats = {"RUSH": (1, 1, 1), "SNIPE": (2, 2, 2), "NADE": (2, 2, 0), "FOE4": (0, 1, 0)}
        for name in who or self.p:
            k, kn, hs = stats.get(name, (0, 0, 0))
            PlayerMatchResult.objects.create(
                match=m, player=self.p[name], team=self.team(name), raw_name=name,
                display_name=name, kills=k, knocks=kn, headshot_knocks=hs, deaths=1,
            )  # fmt: skip

        def hit(kind, t, actor, target, weapon=None, dist=None):
            pos = {"x": 0, "z": 0, "tx": dist, "tz": 0} if dist else {}
            MatchEvent.objects.create(
                match=m, kind=kind, source="DEBUGGER", game_time_s=t,
                actor_entity=self.entity[actor], target_entity=self.entity[target],
                actor_player=self.p[actor], target_player=self.p[target],
                actor_team=self.team(actor), target_team=self.team(target),
                weapon_id=None if blank_weapons else weapon, **pos,
            )  # fmt: skip

        if who is None:
            hit(K.KNOCK, 100, "RUSH", "FOE1")
            hit(K.KILL, 102, "RUSH", "FOE1", RIFLE, dist=8)
            hit(K.KILL, 110, "SNIPE", "FOE2", SNIPER_GUN, dist=150)
            hit(K.KILL, 115, "SNIPE", "FOE4", 0, dist=130)
            hit(K.KILL, 120, "NADE", "FOE3", GRENADE, dist=20)
            hit(K.KILL, 125, "NADE", "FOE4", GRENADE, dist=25)
            hit(K.KNOCK, 130, "FOE4", "ACE")
        spots = {"RUSH": 0, "FOE1": 80, "SNIPE": 5000, "NADE": 3000, "ACE": 7000}
        for name, x in spots.items():
            if who is None or name in who:
                PlayerTrack.objects.create(
                    match=m, entity_id=self.entity[name], player=self.p[name], team=self.team(name),
                    start_s=0, step_s=0.5, points=[[x, 0]] * 1200,
                )  # fmt: skip
        return m


@pytest.fixture
def league():
    lg = League()
    for d in range(4):
        lg.match(WEEK_A + dt.timedelta(days=d))
    return lg


def card(lg, name, week=WEEK_A) -> PlayerCard:
    return PlayerCard.objects.get(player=lg.p[name], week=week)


def stat(c: PlayerCard, key: str) -> dict:
    return next(s for s in c.stats if s["key"] == key)


# -- the maths ------------------------------------------------------------------------------


def test_place_runs_from_worst_to_best_and_ties_share():
    assert cards._place(1, [1, 2, 3]) == 0 and cards._place(3, [1, 2, 3]) == 1
    assert cards._place(2, [2, 2, 1]) == 0.75
    assert cards._place(5, [5]) == 0.5
    assert (cards.rating(0), cards.rating(1)) == (40, 99)


def test_small_samples_are_pulled_to_the_league_average():
    def window(matches, openings):
        w = cards.Window()
        for i in range(matches):
            w.add(cards.MatchLine(openings=openings if i == 0 else 0), 1, False)
        return w

    lucky = window(4, 8)  # one huge night in four matches
    steady = window(12, 0)
    for _ in range(12):
        steady.sums["openings"] += 0.9
    places = cards.rate_windows({1: lucky, 2: steady, 3: window(4, 0)})
    assert places[1]["ENT"] == 1 and places[3]["ENT"] == 0
    # 8 openings in 4 matches is 2 a match; three extra matches at a league average of 0
    # bring it to 8 in 7.
    assert cards._part_value(lucky, cards.PARTS["ENT"][0], {"openings/m": 0}) == 8 / 7
    assert cards.overall([{"key": "ENT", "rating": 80}, {"key": "AIM", "rating": None}], {"ENT": 1})
    assert cards.tier(75) == "gold" and cards.tier(65) == "silver" and cards.tier(64) == "bronze"


# -- building a week ------------------------------------------------------------------------


def test_cards_rate_roles_from_how_they_play(league):
    assert cards.build_week(WEEK_A) == 8
    rush, snipe, nade = card(league, "RUSH"), card(league, "SNIPE"), card(league, "NADE")
    assert rush.role == "RUSHER" and rush.role_suggested
    assert [s["key"] for s in rush.stats] == ["ENT", "CQC", "FIN", "AIM", "TRD", "SUR"]
    assert stat(rush, "ENT")["rating"] == 99 and stat(rush, "CQC")["rating"] == 99
    assert stat(rush, "ENT")["detail"] == "1.0 fights opened a match"

    assert snipe.role == "SNIPER" and stat(snipe, "SNP")["rating"] == 99
    # The kill with no weapon from 130 m counted as a snipe: 2 a match.
    assert stat(snipe, "SNP")["value"] == "2.0"
    assert stat(snipe, "RNG")["rating"] == 99 and "longest 150 m" in stat(snipe, "RNG")["detail"]

    assert nade.role == "GRENADER"
    keys = [s["key"] for s in nade.stats]
    assert keys[-2:] == ["NAD", "UTL"] and stat(nade, "NAD")["extra"]
    assert stat(nade, "NAD")["rating"] == 99

    # Award winners get a Team of the Week card.
    assert set(snipe.totw) == {"player", "sniper"} and rush.totw == ["rusher"]
    assert nade.totw == ["grenader"] and card(league, "ACE").totw == []
    assert rush.overall_change is None and rush.matches == 4 and rush.week_matches == 4
    # From the coach's after-match counts: time alive, and ACE knocked far from their team.
    assert stat(rush, "SUR")["value"] == "9:59"
    ace = card(league, "ACE")
    assert ace.role == "ALL_ROUNDER" and stat(ace, "AWR")["value"] == "100%"


def test_matches_without_weapons_leave_grenades_and_snipes_alone(league):
    cards.build_week(WEEK_A)
    before = stat(card(league, "NADE"), "NAD")["value"]
    league.match(WEEK_A + dt.timedelta(days=5), blank_weapons=True)
    windows = cards.windows_for(WEEK_A)
    nade = windows[league.p["NADE"].pk]
    assert (nade.n, nade.counts["weapons"]) == (5, 4)
    cards.build_week(WEEK_A)
    assert stat(card(league, "NADE"), "NAD")["value"] == before


def test_staff_role_and_weekly_changes(league):
    cards.build_week(WEEK_A)
    Player.objects.filter(pk=league.p["RUSH"].pk).update(card_role="GRENADER")
    league.match(WEEK_B)
    cards.build_week(WEEK_B)
    rush = card(league, "RUSH", WEEK_B)
    assert rush.role == "GRENADER" and not rush.role_suggested and rush.suggested_role == "RUSHER"
    assert rush.overall_change is not None
    assert stat(rush, "ENT")["change"] == 0  # still the league's best opener
    assert rush.matches == 5 and rush.week_matches == 1


def test_no_card_without_matches_that_week_or_enough_matches(league):
    late = player(99, "LATE")
    league.p["LATE"], league.entity["LATE"] = late, 99
    league.match(WEEK_B, who=["LATE", "FOE1"])
    cards.build_week(WEEK_B)
    assert not PlayerCard.objects.filter(player=late).exists()  # 1 match, no card before
    assert not PlayerCard.objects.filter(player=league.p["RUSH"], week=WEEK_B).exists()


def test_rebuild_task_rebuilds_later_weeks(league):
    from apps.results.tasks import rebuild_cards_task

    league.match(WEEK_B)
    assert rebuild_cards_task("2026-10-07") == 16
    assert PlayerCard.objects.filter(week=WEEK_B).count() == 8


# -- the API --------------------------------------------------------------------------------


def staff():
    client = APIClient()
    client.force_authenticate(
        get_user_model().objects.create_user(email="s@tdl.test", is_staff=True)
    )
    return client


def get(path):
    with override_settings(PUBLIC_SITE=True):
        return APIClient().get(f"/api/v1{path}")


def test_cards_api(league):
    league.match(WEEK_B)
    cards.build_week(WEEK_A)
    cards.build_week(WEEK_B)
    data = get("/cards").json()
    assert data["week"] == "2026-10-12" and data["previous"] == "2026-10-05"
    assert data["next"] is None
    top = data["cards"][0]
    assert top["overall"] >= data["cards"][-1]["overall"]
    assert {"name", "photo", "team", "role_label", "tier", "stats"} <= set(top)
    assert top["photo"] is None  # the site shows the blank picture

    snipers = get("/cards?role=sniper&week=2026-10-08").json()
    assert snipers["week"] == "2026-10-05" and [c["name"] for c in snipers["cards"]] == ["SNIPE"]
    assert snipers["cards"][0]["tier"] == "totw" and snipers["next"] == "2026-10-12"
    assert get("/cards?team=bravo").json()["cards"][0]["team"]["slug"] == "bravo"

    one = get(f"/cards/{league.p['RUSH'].pk}").json()
    assert one["week"] == "2026-10-12" and [h["week"] for h in one["history"]] == [
        "2026-10-05",
        "2026-10-12",
    ]
    assert get(f"/cards/{league.p['RUSH'].pk}?week=2026-10-05").json()["week"] == "2026-10-05"
    assert get("/cards/123456").status_code == 404


def test_staff_weights_and_rebuild(league):
    client = staff()
    assert client.get("/api/v1/admin/cards").json()["weights"]["RUSHER"]["CQC"] == 25
    bad = client.put("/api/v1/admin/cards", {"weights": {"RUSHER": {"SNP": 5}}}, format="json")
    assert bad.status_code == 400
    ok = client.put(
        "/api/v1/admin/cards", {"weights": {"RUSHER": {"CQC": 0, "ENT": 100}}}, format="json"
    )
    assert ok.json()["weights"]["RUSHER"]["ENT"] == 100
    assert CardWeights.objects.get().weights == {"RUSHER": {"CQC": 0, "ENT": 100}}
    resp = client.post("/api/v1/admin/cards", {"week": "2026-10-06"}, format="json")
    assert resp.status_code == 202
    # Rusher overall is now the entry rating alone.
    rush = card(league, "RUSH")
    assert rush.overall == stat(rush, "ENT")["rating"]
    assert APIClient().get("/api/v1/admin/cards").status_code in (401, 403)


def test_staff_set_photo_and_role(league):
    client = staff()
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "orange").save(buf, "PNG")
    pid = league.p["ACE"].pk
    resp = client.patch(
        f"/api/v1/admin/players/{pid}",
        {
            "photo": SimpleUploadedFile("ace.png", buf.getvalue(), "image/png"),
            "card_role": "SNIPER",
        },
        format="multipart",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["photo"] and resp.json()["card_role"] == "SNIPER"
    fake = SimpleUploadedFile("x.png", b"<svg onload=alert(1)>", "image/png")
    resp = client.patch(f"/api/v1/admin/players/{pid}", {"photo": fake}, format="multipart")
    assert resp.status_code == 400
    cards.build_week(WEEK_A)
    assert get(f"/cards/{pid}").json()["photo"].endswith(".png")
    # An empty photo removes it: the card goes back to the blank picture.
    resp = client.patch(f"/api/v1/admin/players/{pid}", {"photo": ""}, format="multipart")
    assert resp.status_code == 200, resp.content
    assert resp.json()["photo"] is None and get(f"/cards/{pid}").json()["photo"] is None
