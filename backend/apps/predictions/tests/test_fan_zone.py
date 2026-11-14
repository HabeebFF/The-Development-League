"""The home page's Fan zone: top fan cards, leaders, big wins, the crowd's picks, the rarest
designs and the signed-in fan's own card."""

import datetime as dt
import uuid
from zoneinfo import ZoneInfo

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.accounts.models import StaffProfile
from apps.predictions import fans
from apps.predictions.markets import place_bet
from apps.predictions.models import Bet, Multiple, Wallet
from apps.predictions.services import daily_bonus, wallet_for
from apps.shop import services as shop
from apps.shop.models import CardDesign

from .test_multiples import decide, fan, lg, market, pick, place, staff  # noqa: F401  (fixtures)
from .test_settlement import as_user, make_user

pytestmark = pytest.mark.django_db
URL = "/api/v1/predictions/fan-zone"


@pytest.fixture(autouse=True)
def _on(settings):
    settings.PREDICTIONS_ENABLED = True
    settings.PUBLIC_SITE = True
    cache.delete(fans.CACHE_KEY)
    yield
    cache.delete(fans.CACHE_KEY)


def bet(user, m, team, stake=100):
    o = m.outcomes.get(team__name=team)
    return place_bet(user, market_id=m.pk, outcome_id=o.pk, stake=stake, client_key=uuid.uuid4())[0]


def design(slug, price=100, copies=None) -> CardDesign:
    return CardDesign.objects.create(
        slug=slug,
        name=slug.title(),
        price=price,
        copies=copies,
        parts={"palette": "gold", "pattern": "none", "effect": "none"},
    )


def zone(client=None):
    from rest_framework.test import APIClient

    cache.delete(fans.CACHE_KEY)
    response = (client or APIClient()).get(URL)
    assert response.status_code == 200, response.content
    return response.json()


def test_hidden_while_predictions_are_off(client, settings):
    settings.PREDICTIONS_ENABLED = False
    assert client.get(URL).status_code == 404


def test_top_fans_rank_by_net_dc_so_shopping_never_costs_a_place(lg, staff, fan):  # noqa: F811
    shopper, winner, plain = make_user("shop@tdl.test"), make_user("win@tdl.test"), fan
    for u in (shopper, winner, plain):
        wallet_for(u)
    look = design("test-gold", price=300)
    shop.buy(shopper, look.pk)
    shop.equip(shopper, look.pk)
    m = market(lg, staff, "m1")
    bet(winner, m, "Alpha")  # at 2.00: +100 profit
    decide(m, staff, winners=["Alpha"])

    z = zone()
    assert z["fans"] == 3
    assert [f["name"] for f in z["top"]] == ["win@t", "shop@", "fan@t"]
    assert z["top"][0]["stats"]["net"] == 1100
    second = z["top"][1]
    assert (second["stats"]["balance"], second["stats"]["shop_spent"], second["stats"]["net"]) == (
        700,
        300,
        1000,
    )
    assert second["design"]["slug"] == "test-gold"
    assert z["board"] == []  # only three fans: all on the podium
    assert z["leaders"]["wins"]["name"] == "win@t"
    assert z["leaders"]["accuracy"] is None  # nobody has 10 settled bets


def test_board_lists_places_four_to_eight(db):
    users = [make_user(f"f{i}@tdl.test") for i in range(10)]
    for u in users:
        wallet_for(u)
    z = zone()
    assert [r["rank"] for r in z["board"]] == [4, 5, 6, 7, 8]
    assert len(z["top"]) == 3


def test_accuracy_leader_needs_ten_settled_bets(lg, staff):  # noqa: F811
    sharp, busy = make_user("sharp@tdl.test"), make_user("busy@tdl.test")
    for _ in range(10):
        m = market(lg, staff, "m1")
        bet(sharp, m, "Alpha", stake=10)
        bet(busy, m, "Bravo", stake=10)
        decide(m, staff, winners=["Alpha"])
    z = zone()
    assert z["leaders"]["accuracy"]["name"] == "sharp"
    assert z["leaders"]["accuracy"]["value"] == 1.0


def test_big_wins_are_this_weeks_biggest_profits(lg, staff, fan):  # noqa: F811
    small, big, old = (
        make_user("small@tdl.test"),
        make_user("big@tdl.test"),
        make_user("old@tdl.test"),
    )
    a = market(lg, staff, "m1")
    bet(small, a, "Alpha", stake=100)  # 2.00: +100
    bet(big, a, "Alpha", stake=400)  # 2.00: +400
    bet(old, a, "Alpha", stake=500)
    bet(fan, a, "Bravo", stake=100)  # loses
    decide(a, staff, winners=["Alpha"])
    Bet.objects.filter(user=old).update(settled_at=fans.week_start() - dt.timedelta(hours=1))

    z = zone()
    assert [(w["name"], w["payout"] - w["stake"]) for w in z["big_wins"]] == [
        ("big@t", 400),
        ("small", 100),
    ]
    assert z["big_wins"][0]["pick"] == "Alpha"
    assert z["big_wins"][0]["odds"] == "2.00"
    assert z["week"]["won"] == 2  # the old one settled last week


def test_big_wins_include_multiples(lg, staff, fan):  # noqa: F811
    a, b = market(lg, staff, "m1"), market(lg, staff, "sat")
    place(fan, [pick(a, "Alpha"), pick(b, "Charlie")], stake=100)  # 2.00 x 4.00
    decide(a, staff, winners=["Alpha"])
    decide(b, staff, winners=["Charlie"])
    assert Multiple.objects.get().status == Bet.Status.WON
    win = zone()["big_wins"][0]
    assert (win["pick"], win["stake"], win["payout"], win["odds"]) == (
        "2-pick multiple",
        100,
        800,
        "8.00",
    )


def test_crowd_shows_markets_with_five_or_more_backers(lg, staff):  # noqa: F811
    busy, quiet = market(lg, staff, "m1"), market(lg, staff, "sat")
    users = [make_user(f"c{i}@tdl.test") for i in range(5)]
    for i, u in enumerate(users):
        bet(u, busy, "Alpha" if i < 3 else "Bravo")
    for u in users[:4]:
        bet(u, quiet, "Charlie")
    crowd = zone()["crowd"]
    assert len(crowd) == 1
    assert (crowd[0]["market_id"], crowd[0]["outcome"], crowd[0]["share"], crowd[0]["backers"]) == (
        busy.pk,
        "Alpha",
        0.6,
        5,
    )


def test_crowd_counts_multiple_picks_once_per_fan(lg, staff):  # noqa: F811
    a, b = market(lg, staff, "m1"), market(lg, staff, "sat")
    users = [make_user(f"m{i}@tdl.test") for i in range(5)]
    for u in users:
        place(u, [pick(a, "Delta"), pick(b, "Alpha")], stake=10)
    bet(users[0], a, "Delta")  # same fan again: still one backer
    crowd = {c["market_id"]: c for c in zone()["crowd"]}
    assert crowd[a.pk]["backers"] == 5
    assert crowd[a.pk]["share"] == 1.0


def test_rare_cards_show_owners_and_copies_left(db):
    CardDesign.objects.all().delete()  # the seeded catalogue; nobody owns any here
    diamond = design("diamond", price=500, copies=1)
    vintage = design("vintage", price=200, copies=10)
    design("plain", price=900)  # unlimited: not rare
    a, b = make_user("a@tdl.test"), make_user("b@tdl.test")
    shop.buy(a, diamond.pk)
    shop.buy(a, vintage.pk)
    shop.buy(b, vintage.pk)
    rare = zone()["rare"]
    assert [(r["design"]["slug"], r["owners"], r["left"]) for r in rare] == [
        ("diamond", ["a@tdl"], 0),
        ("vintage", ["b@tdl", "a@tdl"], 8),
    ]


def test_viewer_kinds(db, client):
    visitor = zone(client)
    assert (visitor["viewer"], visitor["me"]) == ("visitor", None)

    boss = make_user("boss@tdl.test")
    StaffProfile.objects.create(user=boss)
    assert zone(as_user(boss))["viewer"] == "staff"

    newbie = make_user("new@tdl.test")
    z = zone(as_user(newbie))
    assert (z["viewer"], z["me"]) == ("new", None)
    assert not Wallet.objects.filter(user=newbie).exists()  # looking never opens a wallet


def test_my_card_place_open_bets_and_bonus(lg, staff, fan, settings):  # noqa: F811
    settings.PREDICTIONS_DAILY_BONUS = 200
    rich = make_user("rich@tdl.test")
    wallet_for(rich)
    m = market(lg, staff, "m1")
    bet(rich, m, "Alpha", stake=100)
    decide(m, staff, winners=["Alpha"])
    wallet_for(fan)
    bet(fan, market(lg, staff, "sat"), "Bravo", stake=50)

    me = zone(as_user(fan))["me"]
    assert (me["rank"], me["open_bets"], me["bonus_ready"], me["daily_bonus"]) == (2, 1, True, 200)
    assert me["stats"]["balance"] == 950
    assert wallet_for(fan).balance == 950  # the home page gives no coins

    daily_bonus(wallet_for(fan))
    me = zone(as_user(fan))["me"]
    assert me["bonus_ready"] is False
    assert me["rank"] == 1  # 1,150 now, ahead of rich's 1,100


def test_week_runs_monday_to_sunday_in_lagos():
    lagos = ZoneInfo("Africa/Lagos")
    sunday_late = dt.datetime(2026, 11, 15, 23, 30, tzinfo=lagos)
    monday_early = dt.datetime(2026, 11, 16, 0, 10, tzinfo=lagos)
    assert fans.week_start(sunday_late) == dt.datetime(2026, 11, 9, tzinfo=lagos)
    assert fans.week_start(monday_early.astimezone(dt.UTC)) == dt.datetime(
        2026, 11, 16, tzinfo=lagos
    )


def test_week_numbers_count_bets_and_stakes(lg, staff, fan):  # noqa: F811
    a, b = market(lg, staff, "m1"), market(lg, staff, "sat")
    bet(fan, a, "Alpha", stake=100)
    place(fan, [pick(a, "Bravo"), pick(b, "Charlie")], stake=30)
    old = bet(make_user("o@tdl.test"), a, "Alpha", stake=500)
    Bet.objects.filter(pk=old.pk).update(placed_at=timezone.now() - dt.timedelta(days=8))
    week = zone()["week"]
    assert (week["bets"], week["staked"]) == (2, 130)


def test_shared_part_is_cached(db, client):
    make_user("one@tdl.test")
    wallet_for(make_user("two@tdl.test"))
    assert client.get(URL).json()["fans"] == 1
    wallet_for(make_user("three@tdl.test"))
    assert client.get(URL).json()["fans"] == 1  # cached for a minute
    cache.delete(fans.CACHE_KEY)
    assert client.get(URL).json()["fans"] == 2
