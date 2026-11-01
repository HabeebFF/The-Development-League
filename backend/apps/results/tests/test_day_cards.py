"""Daily player cards: built from one day's matches, shown only to the player's own team."""

import datetime as dt

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Membership
from apps.results import cards, day_cards
from apps.results.models import PlayerCard, PlayerDayCard, PlayerMatchRating
from apps.results.tests.test_cards import League

pytestmark = pytest.mark.django_db
DAY, OTHER = dt.date(2026, 10, 3), dt.date(2026, 10, 4)


@pytest.fixture(autouse=True)
def fresh_cache():
    cache.clear()


@pytest.fixture
def league():
    return League()


def card(name, lg, day=DAY):
    return PlayerDayCard.objects.get(player=lg.p[name], day=day)


def client_for(email, team=None, **extra):
    user = get_user_model().objects.create_user(email=email, **extra)
    if team:
        Membership.objects.create(user=user, team=team)
    c = APIClient()
    c.force_authenticate(user)
    return c


def test_day_card_uses_that_day_only(league):
    for _ in range(3):
        league.match(DAY)
    league.match(OTHER)
    assert day_cards.build_day(DAY) == 8
    rush = card("RUSH", league)
    assert rush.matches == 3 and rush.kills == 3 and rush.knocks == 3
    assert rush.overall is not None and rush.team == league.alpha
    # No role set: the day's numbers suggest one, with that role's stats.
    assert rush.role == "RUSHER"
    assert [s["key"] for s in rush.stats] == cards.ROLE_STATS["RUSHER"]
    # SNIPE's two snipes a match beat everyone that day.
    assert card("SNIPE", league).role == "SNIPER"
    snipe = {s["key"]: s for s in card("SNIPE", league).stats}
    assert snipe["SNP"]["rating"] == 99
    # No damage logged: that stat has no number, but the card still has an overall.
    assert snipe["DMG"]["rating"] is None and snipe["DMG"]["stale"]
    assert rush.rules == day_cards.RULES


def test_one_match_is_not_enough_for_a_card(league):
    league.match(DAY)
    league.match(DAY, who=["SNIPE", "FOE1"])
    day_cards.build_day(DAY)
    rush = card("RUSH", league)
    assert rush.matches == 1 and rush.overall is None and rush.stats == []
    assert rush.kills == 1
    assert card("SNIPE", league).overall is not None


def test_role_comes_from_the_weekly_card_and_staff(league):
    league.match(DAY)
    league.match(DAY)
    PlayerCard.objects.create(
        player=league.p["ACE"], week=dt.date(2026, 9, 26), role="SNIPER", overall=70, matches=4
    )
    league.p["RUSH"].card_role = "RUSHER"
    league.p["RUSH"].save()
    day_cards.build_day(DAY)
    assert card("ACE", league).role == "SNIPER"
    assert card("RUSH", league).role == "RUSHER"
    assert [s["key"] for s in card("RUSH", league).stats][0] == "ENT"


def test_rating_is_the_days_average(league):
    a, b = league.match(DAY), league.match(DAY)
    for m, r in ((a, 6.0), (b, 8.0)):
        PlayerMatchRating.objects.create(
            match=m, player=league.p["RUSH"], rating=r, raw=r, stamp="x"
        )
    day_cards.build_day(DAY)
    assert card("RUSH", league).rating == 7.0


def test_refresh_builds_only_changed_days(league):
    m = league.match(DAY)
    league.match(DAY)
    gone = league.match(OTHER)
    assert day_cards.refresh() == 2
    assert day_cards.refresh() == 0
    m.save()  # a re-upload changes the match
    assert day_cards.refresh() == 1
    assert day_cards.refresh(force=True) == 2
    # A day whose matches are gone loses its cards.
    gone.delete()
    day_cards.refresh()
    assert not PlayerDayCard.objects.filter(day=OTHER).exists()
    assert PlayerDayCard.objects.filter(day=DAY).exists()


def test_new_matches_build_day_cards(league):
    """Uploading matches rates them, and the ratings step builds the day's cards."""
    from apps.results.tasks import refresh_ratings_task

    league.match(DAY)
    league.match(DAY)
    refresh_ratings_task(league.stage.season_id)
    rush = card("RUSH", league)
    assert rush.overall is not None and rush.rating is not None


def test_command(league):
    league.match(DAY)
    league.match(DAY)
    call_command("build_day_cards", "--all")
    call_command("build_day_cards", "--date", DAY.isoformat())
    assert PlayerDayCard.objects.filter(day=DAY).count() == 8


# -- who can see them -----------------------------------------------------------------------


def test_team_members_see_their_own_team(league):
    league.match(DAY)
    league.match(DAY)
    league.match(OTHER)
    league.match(OTHER, who=["RUSH", "FOE1"])
    day_cards.refresh()
    member = client_for("a@tdl.test", league.alpha)
    url = f"/api/v1/teams/{league.alpha.slug}/day-cards"
    data = member.get(url).json()
    assert data["date"] == OTHER.isoformat() and data["previous"] == DAY.isoformat()
    assert data["days"] == [OTHER.isoformat(), DAY.isoformat()]
    assert {c["name"] for c in data["cards"]} == {"RUSH"}
    assert {c["name"] for c in data["short"]} == {"SNIPE", "NADE", "ACE"}
    data = member.get(url, {"date": DAY.isoformat()}).json()
    assert {c["name"] for c in data["cards"]} == {"RUSH", "SNIPE", "NADE", "ACE"}
    assert data["next"] == OTHER.isoformat()
    top = data["cards"][0]
    assert top["overall"] == max(c["overall"] for c in data["cards"])
    assert top["tier"] in ("gold", "silver", "bronze") and top["day"] == DAY.isoformat()
    assert {"FIN", "AIM"} <= {s["key"] for s in top["stats"]}


def test_other_teams_and_fans_cannot_see_them(league):
    league.match(DAY)
    league.match(DAY)
    day_cards.refresh()
    url = f"/api/v1/teams/{league.alpha.slug}/day-cards"
    assert client_for("b@tdl.test", league.bravo).get(url).status_code == 403
    assert client_for("fan@tdl.test").get(url).status_code == 403
    with override_settings(PUBLIC_SITE=True):
        assert APIClient().get(url).status_code in (401, 403)
    gone = client_for("old@tdl.test", league.alpha)
    Membership.objects.filter(user__email="old@tdl.test").update(is_active=False)
    assert gone.get(url).status_code == 403
    staff = client_for("s@tdl.test", is_staff=True)
    assert len(staff.get(url).json()["cards"]) == 4
    assert staff.get(f"/api/v1/teams/{league.bravo.slug}/day-cards").json()["cards"]


def test_hidden_cards_are_left_out(league):
    league.match(DAY)
    league.match(DAY)
    day_cards.refresh()
    league.p["ACE"].hide_card = True
    league.p["ACE"].save()
    data = (
        client_for("a@tdl.test", league.alpha)
        .get(f"/api/v1/teams/{league.alpha.slug}/day-cards")
        .json()
    )
    assert "ACE" not in {c["name"] for c in data["cards"] + data["short"]}


def test_compared_with_the_weekly_card_once_it_is_out(league):
    league.match(DAY)
    league.match(DAY)
    day_cards.refresh()
    # Out: last week's card. Not out yet: this week's (in the test's "now" it's long out,
    # so the newest released one wins).
    PlayerCard.objects.create(
        player=league.p["RUSH"], week=dt.date(2026, 9, 26), role="RUSHER", overall=60, matches=4
    )
    data = (
        client_for("a@tdl.test", league.alpha)
        .get(f"/api/v1/teams/{league.alpha.slug}/day-cards")
        .json()
    )
    rush = next(c for c in data["cards"] if c["name"] == "RUSH")
    assert rush["weekly_overall"] == 60
    assert rush["overall_change"] == rush["overall"] - 60
