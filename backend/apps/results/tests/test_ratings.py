"""Player ratings out of 10: one match, days and sessions, keeping them fresh, and the API."""

import datetime as dt
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.league.models import Match
from apps.results import ratings
from apps.results.models import PlayerMatchRating, PlayerMatchResult, RatingPoints
from apps.results.tests.test_cards import WEEK_A, League

pytestmark = pytest.mark.django_db
PTS = ratings.DEFAULT_POINTS


@pytest.fixture(autouse=True)
def fresh_cache():
    cache.clear()


def line(**kw):
    base = dict(kills=0, knocks=0, headshots=0, openings=0, trades=0, alone_downs=0,
                first_down=False)  # fmt: skip
    return SimpleNamespace(**{**base, **kw})


def rated(lg, name, match) -> PlayerMatchRating:
    return PlayerMatchRating.objects.get(player=lg.p[name], match=match)


# -- the maths ------------------------------------------------------------------------------


def test_examples():
    # A quiet match: one knock, team 10th, out early.
    quiet = ratings.rate_line(line(knocks=1), 10, 0.1, PTS)
    assert quiet["rating"] == ratings.one_decimal(5.7 + 0.08 - 0.2 - 0.48) == 5.1
    # A solid one: 2 kills, 3 knocks, team 5th, alive to the end.
    solid = ratings.rate_line(line(kills=2, knocks=3), 5, 1.0, PTS)
    assert solid["rating"] == ratings.one_decimal(5.7 + 0.36 + 0.24 + 0.3 + 0.6) == 7.2
    # The best: 9 kills, 11 knocks, Booyah. Above the ceiling, so 10.0.
    huge = ratings.rate_line(line(kills=9, knocks=11, headshots=3, openings=4), 1, 1.0, PTS)
    assert huge["raw"] > 10 and huge["rating"] == 10.0


def test_floor_penalties_and_missing_data():
    bad = ratings.rate_line(line(alone_downs=9, first_down=True), 15, 0.0, PTS)
    assert bad["rating"] == 3.0
    keys = {p["key"]: p["points"] for p in bad["parts"]}
    assert keys == {"placement": -0.5, "survival": -0.6, "alone_downs": -2.25, "first_down": -0.2}
    # No placement, no time alive: nothing counts for or against.
    assert ratings.rate_line(line(), None, None, PTS) == {"rating": 5.7, "raw": 5.7, "parts": []}


def test_placement_table_and_bands():
    table = PTS["placement"]
    assert [ratings.place_points(p, table) for p in (1, 2, 3, 7, 9, 13, 20)] == [
        1.0, 0.7, 0.5, 0.0, -0.1, -0.5, -0.5,
    ]  # fmt: skip
    assert [ratings.band(x) for x in (5.9, 6.0, 7.4, 8.0, 9.0, None)] == [
        "red", "orange", "green", "blue", "gold", None,
    ]  # fmt: skip
    assert ratings.one_decimal(7.25) == 7.3 and ratings.one_decimal(6.04) == 6.0


# -- a real match ---------------------------------------------------------------------------


@pytest.fixture
def lg():
    return League()


def test_rate_match_uses_scoreboard_placement_and_time_alive(lg):
    m = lg.match(WEEK_A)
    Match.objects.filter(pk=m.pk).update(duration_s=600)
    m.refresh_from_db()
    assert ratings.rate_match(m) == 8
    rush = rated(lg, "RUSH", m)
    parts = {p["key"]: p for p in rush.parts}
    # 1 kill, 1 knock (a headshot), opened the fight, team won, tracked to the end (600 s).
    assert parts["kills"]["points"] == 0.18 and parts["openings"]["count"] == 1
    assert parts["placement"]["points"] == 1.0
    assert parts["survival"]["points"] == 0.6
    assert rush.rating == ratings.one_decimal(5.7 + 0.18 + 0.08 + 0.04 + 0.08 + 1.0 + 0.6)
    # FOE2 had no replay track: out when killed (110 s of 600), team second.
    foe2 = {p["key"]: p for p in rated(lg, "FOE2", m).parts}
    assert foe2["survival"]["count"] == 0.18 and foe2["placement"]["points"] == 0.7
    # ACE was the team's first player down, and knocked far from everyone.
    ace = {p["key"]: p["points"] for p in rated(lg, "ACE", m).parts}
    assert ace.get("first_down") == -0.2


def test_refresh_only_rates_what_changed_and_drops_unpublished(lg):
    m1, m2 = lg.match(WEEK_A), lg.match(WEEK_A + dt.timedelta(days=1))
    assert ratings.refresh() == 2
    assert ratings.refresh() == 0
    PlayerMatchResult.objects.filter(match=m1, player=lg.p["RUSH"]).update(kills=5)
    assert ratings.refresh() == 1
    assert rated(lg, "RUSH", m1).kills == 5
    Match.objects.filter(pk=m2.pk).update(status=Match.Status.DRAFT)
    ratings.refresh()
    assert not PlayerMatchRating.objects.filter(match=m2).exists()
    # New points: everything again.
    RatingPoints.objects.create(points={"kill": 1.0})
    assert ratings.refresh() == 1


def test_publishing_rates_through_the_standings_rebuild(lg):
    from apps.results.tasks import rebuild_standings_task

    m = lg.match(WEEK_A)
    rebuild_standings_task(m.match_day.stage.season_id)
    assert PlayerMatchRating.objects.filter(match=m).count() == 8


# -- days and sessions ----------------------------------------------------------------------


def two_sessions(lg):
    """Two sessions on one day (8PM and 10PM) and one the next day."""
    a = lg.match(WEEK_A)
    b = lg.match(WEEK_A)
    Match.objects.filter(pk=b.pk).update(started_at=a.started_at + dt.timedelta(hours=2))
    c = lg.match(WEEK_A + dt.timedelta(days=1))
    ratings.refresh()
    return a, b, c


def test_day_averages_both_sessions_and_picks_player_of_the_day(lg):
    a, b, c = two_sessions(lg)
    day = ratings.for_day(WEEK_A)
    assert day["matches"] == 2 and [s["id"] for s in day["sessions"]] == [
        a.match_day_id, b.match_day_id,
    ]  # fmt: skip
    rush = next(p for p in day["players"] if p["player"] == "RUSH")
    assert rush["matches"] == 2 and len(rush["ratings"]) == 2
    mine = PlayerMatchRating.objects.filter(player=lg.p["RUSH"], match__in=[a, b])
    assert rush["rating"] == ratings.one_decimal(sum(r.rating for r in mine) / 2)
    top = day["players"][0]
    assert day["star"] == top["player_id"] and top["star"] and day["need"] == 2
    assert day["previous"] is None and day["next"] == WEEK_A + dt.timedelta(days=1)

    one = ratings.for_day(WEEK_A, b.match_day_id)
    assert one["matches"] == 1 and one["session"] == b.match_day_id
    latest = ratings.for_day(None)
    assert latest["date"] == WEEK_A + dt.timedelta(days=1) and latest["previous"] == WEEK_A


def test_player_of_the_day_needs_enough_matches(lg):
    lg.match(WEEK_A)
    lg.match(WEEK_A, who=["RUSH", "FOE1"])
    ratings.refresh()
    # Make a one-match player the best average: still not Player of the Day.
    PlayerMatchRating.objects.filter(player=lg.p["NADE"]).update(rating=9.9)
    day = ratings.for_day(WEEK_A)
    assert day["players"][0]["player"] == "NADE" and day["need"] == 2
    assert day["star"] == lg.p["RUSH"].pk


def test_player_history(lg):
    two_sessions(lg)
    from django.utils import timezone

    hist = ratings.for_player(lg.p["RUSH"])
    assert [d["date"] for d in hist["days"]] == [WEEK_A, WEEK_A + dt.timedelta(days=1)]
    assert hist["days"][0]["matches"] == 2 and hist["all"]["matches"] == 3
    if timezone.localdate() - WEEK_A > dt.timedelta(days=30):
        assert hist["month"] is None


# -- API ------------------------------------------------------------------------------------


def staff_client():
    user = get_user_model().objects.create_user(
        email="staff@tdl.test", password="pw-123456", is_staff=True
    )
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_public_api(lg):
    a, b, c = two_sessions(lg)
    api = APIClient()
    day = api.get("/api/v1/ratings", {"date": WEEK_A.isoformat()}).json()
    assert day["matches"] == 2 and day["players"][0]["band"]
    assert api.get("/api/v1/ratings").json()["date"] == str(WEEK_A + dt.timedelta(days=1))
    sess = api.get("/api/v1/ratings", {"session": b.match_day_id}).json()
    assert sess["matches"] == 1 and sess["session"] == b.match_day_id
    assert sess["date"] == str(WEEK_A) and len(sess["sessions"]) == 2
    match = api.get("/api/v1/ratings", {"match": a.pk}).json()
    assert match["base"] == 5.7 and len(match["players"]) == 8
    assert match["players"][0]["rating"] >= match["players"][-1]["rating"]
    assert match["players"][0]["parts"]
    hist = api.get(f"/api/v1/ratings/player/{lg.p['RUSH'].pk}").json()
    assert len(hist["days"]) == 2
    assert api.get("/api/v1/ratings", {"match": 999999}).status_code == 404


def test_staff_points(lg):
    m = lg.match(WEEK_A)
    ratings.refresh()
    before = rated(lg, "RUSH", m).rating
    assert APIClient().get("/api/v1/admin/ratings").status_code in (401, 403)
    staff = staff_client()
    got = staff.get("/api/v1/admin/ratings").json()
    assert got["points"]["kill"] == 0.18
    bad = staff.put("/api/v1/admin/ratings", {"points": {"kill": 9}}, format="json")
    assert bad.status_code == 400
    upside_down = {"points": {"floor": 9.5, "ceiling": 9}}
    bad = staff.put("/api/v1/admin/ratings", upside_down, format="json")
    assert bad.status_code == 400
    bad = staff.put("/api/v1/admin/ratings", {"points": {"placement": ["x"]}}, format="json")
    assert bad.status_code == 400
    saved = staff.put(
        "/api/v1/admin/ratings", {"points": {"base": 4.7, "potd_min": 3}}, format="json"
    )
    assert saved.status_code == 200 and saved.json()["points"]["base"] == 4.7
    # Saving rates everything again (the task runs when the request's transaction commits).
    ratings.refresh()
    assert rated(lg, "RUSH", m).rating == ratings.one_decimal(before - 1.0)
    assert staff.post("/api/v1/admin/ratings").status_code == 202
