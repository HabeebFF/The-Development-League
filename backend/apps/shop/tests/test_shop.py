"""Card shop: buying with DC, limited copies, equipping, refunds, gifts, the designs on cards,
the net-DC leaderboard and the daily bonus."""

import datetime as dt
import threading

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.accounts.models import StaffProfile, User
from apps.league.models import Player, Team
from apps.predictions.models import LedgerEntry
from apps.predictions.services import Kind, check_wallet, wallet_for
from apps.results.models import PlayerCard
from apps.shop import services
from apps.shop.models import CardDesign, Equipped, OwnedDesign

pytestmark = pytest.mark.django_db
PASSWORD = "a-Long-password-42"
START = 50_000


@pytest.fixture(autouse=True)
def _on(settings):
    settings.PREDICTIONS_ENABLED = True
    settings.PUBLIC_SITE = True
    # Designs cost 1,500 to 1,000,000 DC; start rich enough to buy the cheaper ones.
    settings.PREDICTIONS_INITIAL_COINS = START


def make_user(email="fan@tdl.test", name="Fan") -> User:
    return User.objects.create_user(email=email, password=PASSWORD, display_name=name)


def as_user(user) -> APIClient:
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def fan():
    return make_user()


@pytest.fixture
def staff():
    user = make_user("staff@tdl.test", "Staff")
    StaffProfile.objects.create(user=user)
    return user


def design(slug, **kw) -> CardDesign:
    return CardDesign.objects.get(slug=slug) if not kw else CardDesign.objects.create(
        slug=slug, name=slug.title(), price=kw.pop("price", 100),
        parts={"palette": "gold", "pattern": "none", "effect": "none"}, **kw,
    )  # fmt: skip


def buy(client, d, **body):
    return client.post(f"/api/v1/shop/designs/{d.pk}/buy", body, format="json")


# -- catalogue ---------------------------------------------------------------------------------


def test_starting_designs_are_in_the_shop_for_anyone():
    rows = APIClient().get("/api/v1/shop/designs").json()["designs"]
    assert [(r["slug"], r["price"], r["rarity"]) for r in rows] == [
        ("carbon-black", 1500, "COMMON"),
        ("ocean-blue", 1500, "COMMON"),
        ("molten-gold", 5000, "RARE"),
        ("neon-cyan", 5000, "RARE"),
        ("crimson", 5000, "RARE"),
        ("lava-flow", 15000, "EPIC"),
        ("holo-shine", 15000, "EPIC"),
        ("champion", 40000, "LEGENDARY"),
        ("vintage", 100000, "VINTAGE"),
        ("diamond", 1000000, "DIAMOND"),
    ]
    by_slug = {r["slug"]: r for r in rows}
    assert (by_slug["champion"]["copies"], by_slug["champion"]["left"]) == (20, 20)
    assert (by_slug["vintage"]["copies"], by_slug["diamond"]["copies"]) == (10, 1)


def test_shop_is_hidden_while_predictions_are_off(settings):
    settings.PREDICTIONS_ENABLED = False
    assert APIClient().get("/api/v1/shop/designs").status_code == 404


def test_hidden_or_ended_designs_leave_the_shop_but_owners_still_see_theirs(fan):
    gold = design("molten-gold")
    services.buy(fan, gold.pk)
    gold.on_sale = False
    gold.save()
    CardDesign.objects.filter(slug="crimson").update(
        sale_ends=dt.datetime(2020, 1, 1, tzinfo=dt.UTC)
    )
    public = [r["slug"] for r in APIClient().get("/api/v1/shop/designs").json()["designs"]]
    assert "molten-gold" not in public and "crimson" not in public
    mine = {r["slug"]: r for r in as_user(fan).get("/api/v1/shop/designs").json()["designs"]}
    assert mine["molten-gold"]["owned"] and not mine["molten-gold"]["available"]
    assert buy(as_user(make_user("b@tdl.test")), gold).status_code == 400


# -- buying ------------------------------------------------------------------------------------


def test_buying_takes_the_price_through_the_ledger(fan):
    resp = buy(as_user(fan), design("molten-gold"))
    assert resp.status_code == 201, resp.content
    assert resp.json()["balance"] == START - 5000
    wallet = wallet_for(fan)
    entry = wallet.entries.get(kind=Kind.PURCHASE)
    assert (entry.amount, entry.balance_after) == (-5000, START - 5000)
    assert OwnedDesign.objects.get(user=fan).entry == entry
    assert check_wallet(wallet) == []


def test_cant_buy_the_same_design_twice(fan):
    c = as_user(fan)
    assert buy(c, design("ocean-blue")).status_code == 201
    again = buy(c, design("ocean-blue"))
    assert again.status_code == 400 and "already own" in again.json()["detail"]
    assert wallet_for(fan).balance == START - 1500


def test_cant_buy_without_enough_dc_and_nothing_is_kept(fan):
    c = as_user(fan)
    resp = buy(c, design("diamond"))  # 1,000,000 DC
    assert resp.status_code == 400 and "Not enough DC" in resp.json()["detail"]
    assert not OwnedDesign.objects.filter(design__slug="diamond").exists()
    assert wallet_for(fan).balance == START


def test_staff_cant_buy(staff):
    resp = buy(as_user(staff), design("ocean-blue"))
    assert resp.status_code == 403
    with pytest.raises(services.ShopError):
        services.buy(staff, design("ocean-blue").pk)


def test_signed_out_cant_buy():
    assert buy(APIClient(), design("ocean-blue")).status_code in (401, 403)


def test_limited_copies_get_numbers_and_sell_out(fan):
    rare = design("limited", price=10, copies=2)
    a, b = make_user("a@tdl.test"), make_user("b@tdl.test")
    assert services.buy(a, rare.pk).copy_number == 1
    assert services.buy(b, rare.pk).copy_number == 2
    with pytest.raises(services.ShopError, match="Sold out"):
        services.buy(fan, rare.pk)
    assert wallet_for(fan).balance == START


@pytest.mark.django_db(transaction=True)
def test_limited_copies_cant_be_oversold_when_many_buy_at_once():
    rare = design("rush", price=50, copies=3)
    users = [make_user(f"u{n}@tdl.test") for n in range(10)]
    for u in users:
        wallet_for(u)
    results = []

    def go(user):
        try:
            services.buy(user, rare.pk)
            results.append("ok")
        except services.ShopError:
            results.append("refused")
        finally:
            connection.close()

    threads = [threading.Thread(target=go, args=(u,)) for u in users]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("ok") == 3
    copies = sorted(OwnedDesign.objects.filter(design=rare).values_list("copy_number", flat=True))
    assert copies == [1, 2, 3]
    assert LedgerEntry.objects.filter(kind=Kind.PURCHASE).count() == 3


@pytest.mark.django_db(transaction=True)
def test_one_wallet_cant_spend_the_same_dc_twice_at_once():
    fan = make_user()
    wallet_for(fan)
    pricey = [design(f"d{n}", price=20_000) for n in range(5)]
    results = []

    def go(d):
        try:
            services.buy(fan, d.pk)
            results.append("ok")
        except services.ShopError:
            results.append("refused")
        finally:
            connection.close()

    threads = [threading.Thread(target=go, args=(d,)) for d in pricey]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("ok") == 2
    wallet = wallet_for(fan)
    assert wallet.balance == START - 40_000 and check_wallet(wallet) == []


# -- equipping ---------------------------------------------------------------------------------


def test_equip_only_what_you_own_and_go_back_to_default(fan):
    c = as_user(fan)
    gold, cyan = design("molten-gold"), design("neon-cyan")
    assert c.post("/api/v1/shop/equip", {"design": gold.pk}, format="json").status_code == 400
    assert buy(c, gold, equip=True).json()["equipped"]
    assert Equipped.objects.get(user=fan).design == gold
    assert c.post("/api/v1/shop/equip", {"design": cyan.pk}, format="json").status_code == 400
    assert c.post("/api/v1/shop/equip", {"design": None}, format="json").json() == {
        "equipped": None
    }


def test_me_shows_fan_card_owned_designs_and_net_dc(fan):
    team = Team.objects.create(name="Alpha")
    c = as_user(fan)
    buy(c, design("champion"), equip=True)
    resp = c.patch("/api/v1/shop/me", {"favourite_team": team.slug}, format="json").json()
    assert resp["favourite_team"]["slug"] == team.slug
    assert resp["design"]["slug"] == "champion" and resp["design"]["copy_number"] == 1
    assert resp["stats"]["balance"] == START - 40_000
    assert resp["stats"]["shop_spent"] == 40_000 and resp["stats"]["net"] == START
    assert [o["design"]["slug"] for o in resp["owned"]] == ["champion"]
    assert resp["player_id"] is None


# -- designs on cards --------------------------------------------------------------------------


@pytest.fixture
def carded(fan):
    team = Team.objects.create(name="Alpha")
    ace = Player.objects.create(
        game_uid=1, current_name_raw="ACE", display_name="ACE", search_name="ace",
        current_team=team, user=fan,
    )  # fmt: skip
    other = Player.objects.create(
        game_uid=2, current_name_raw="BOB", display_name="BOB", search_name="bob",
        current_team=team,
    )  # fmt: skip
    for p, ovr in ((ace, 80), (other, 70)):
        PlayerCard.objects.create(
            player=p, week=dt.date(2026, 10, 3), team=team, role="RUSHER", overall=ovr,
            matches=4, rules="t",
        )  # fmt: skip
    return ace


def test_linked_players_card_wears_their_design(fan, carded):
    services.buy(fan, design("lava-flow").pk)
    services.equip(fan, design("lava-flow").pk)
    cards = APIClient().get("/api/v1/cards?week=2026-10-03").json()["cards"]
    by_name = {c["name"]: c for c in cards}
    assert by_name["ACE"]["design"]["slug"] == "lava-flow"
    assert by_name["ACE"]["tier"] == "gold"  # the tier still shows
    assert by_name["BOB"]["design"] is None
    one = APIClient().get(f"/api/v1/cards/{carded.pk}")
    assert one.status_code == 200 and one.json()["design"]["slug"] == "lava-flow"
    me = as_user(fan).get("/api/v1/shop/me").json()
    assert me["player_id"] == carded.pk


def test_refund_gives_coins_back_and_takes_the_design_off(fan, staff, carded):
    lava = design("lava-flow")
    owned = services.buy(fan, lava.pk)
    services.equip(fan, lava.pk)
    resp = as_user(staff).post(f"/api/v1/admin/shop/sales/{owned.pk}/refund")
    assert resp.status_code == 200 and resp.json()["refunded_at"]
    wallet = wallet_for(fan)
    assert wallet.balance == START and check_wallet(wallet) == []
    assert wallet.entries.get(kind=Kind.SHOP_REFUND).actor == staff
    assert Equipped.objects.get(user=fan).design is None
    again = as_user(staff).post(f"/api/v1/admin/shop/sales/{owned.pk}/refund")
    assert again.status_code == 400
    # They can buy it again later.
    assert services.buy(fan, lava.pk).copy_number == 1


def test_refunded_copy_number_is_given_out_again(fan):
    rare = design("few", price=10, copies=2)
    a = make_user("a@tdl.test")
    first = services.buy(a, rare.pk)
    services.buy(make_user("b@tdl.test"), rare.pk)
    services.refund(first.pk, None)
    assert services.buy(fan, rare.pk).copy_number == 1


def test_gift_is_free_and_counts_as_a_copy(fan, staff):
    resp = as_user(staff).post(
        "/api/v1/admin/shop/gift",
        {"email": fan.email, "design": design("champion").pk, "note": "TOTW"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["gift"] and resp.json()["price_paid"] == 0
    assert wallet_for(fan).balance == START
    shop = {r["slug"]: r for r in APIClient().get("/api/v1/shop/designs").json()["designs"]}
    assert shop["champion"]["left"] == 19
    gift_to_staff = as_user(staff).post(
        "/api/v1/admin/shop/gift",
        {"email": staff.email, "design": design("champion").pk},
        format="json",
    )
    assert gift_to_staff.status_code == 400


def test_staff_can_take_a_design_off_someones_card(fan, staff):
    services.buy(fan, design("crimson").pk)
    services.equip(fan, design("crimson").pk)
    resp = as_user(staff).post("/api/v1/admin/shop/unequip", {"user": fan.pk}, format="json")
    assert resp.json() == {"unequipped": True}
    assert OwnedDesign.objects.filter(user=fan, refunded_at__isnull=True).exists()


def test_special_cards_keep_their_own_look(fan, carded):
    from apps.league import views

    services.buy(fan, design("lava-flow").pk)
    services.equip(fan, design("lava-flow").pk)
    card = PlayerCard.objects.get(player=carded)
    plain = views._card(card, None)
    assert plain["design"]["slug"] == "lava-flow"
    src = open(views.__file__).read()
    for tier in ("totw", "rising", "icon", "totm"):
        assert f'"tier": "{tier}"' in src
    assert src.count('"design": None') >= 4


# -- staff designs -----------------------------------------------------------------------------


def test_staff_add_edit_and_cant_delete_an_owned_design(fan, staff):
    c = as_user(staff)
    resp = c.post(
        "/api/v1/admin/shop/designs",
        {"slug": "emerald", "name": "Emerald", "rarity": "RARE", "price": 300,
         "parts": {"palette": "emerald", "pattern": "hex", "effect": "glow"}},
        format="json",
    )  # fmt: skip
    assert resp.status_code == 201, resp.content
    bad = c.post(
        "/api/v1/admin/shop/designs",
        {"slug": "x", "name": "X", "price": 10, "parts": {"palette": "pink"}},
        format="json",
    )
    assert bad.status_code == 400 and "palette" in str(bad.json())
    free = c.post(
        "/api/v1/admin/shop/designs",
        {"slug": "y", "name": "Y", "price": 0, "parts": {"palette": "gold"}},
        format="json",
    )
    assert free.status_code == 400
    services.buy(fan, design("ocean-blue").pk)
    gone = c.delete(f"/api/v1/admin/shop/designs/{design('ocean-blue').pk}")
    assert gone.status_code == 400
    assert c.delete(f"/api/v1/admin/shop/designs/{resp.json()['id']}").status_code == 204
    assert set(c.get("/api/v1/admin/shop/designs/parts").json()) == {
        "palette",
        "pattern",
        "effect",
    }
    sales = c.get("/api/v1/admin/shop/sales").json()
    assert sales["totals"] == {"copies": 1, "dc": 1500}
    assert sales["results"][0]["email"] == fan.email


def test_fans_cant_use_staff_shop_tools(fan):
    c = as_user(fan)
    assert c.get("/api/v1/admin/shop/sales").status_code == 403
    assert c.post("/api/v1/admin/shop/designs", {}, format="json").status_code == 403


# -- leaderboard and daily bonus ---------------------------------------------------------------


def test_leaderboard_ranks_by_net_dc_so_shopping_costs_no_place(fan):
    saver = make_user("saver@tdl.test", "Saver")
    wallet_for(saver)
    services.buy(fan, design("champion").pk)
    services.equip(fan, design("champion").pk)
    rows = APIClient().get("/api/v1/predictions/leaderboard?metric=balance").json()["rows"]
    by_name = {r["name"]: r for r in rows}
    assert by_name["Fan"]["net"] == by_name["Saver"]["net"] == START
    assert by_name["Fan"]["balance"] == START - 40_000 and by_name["Fan"]["shop_spent"] == 40_000
    assert by_name["Fan"]["design"]["slug"] == "champion"
    assert by_name["Saver"]["design"] is None


def test_daily_bonus_once_per_lagos_day(fan, settings, monkeypatch):
    settings.PREDICTIONS_DAILY_BONUS = 200
    from apps.predictions import services as coin

    c = as_user(fan)
    monkeypatch.setattr(coin, "lagos_today", lambda: dt.date(2026, 11, 13))
    first = c.get("/api/v1/predictions/wallet").json()
    assert (first["balance"], first["bonus"]) == (START + 200, 200)
    again = c.get("/api/v1/predictions/wallet").json()
    assert (again["balance"], again["bonus"]) == (START + 200, 0)
    monkeypatch.setattr(coin, "lagos_today", lambda: dt.date(2026, 11, 14))
    assert c.get("/api/v1/predictions/wallet").json()["balance"] == START + 400
    assert check_wallet(wallet_for(fan)) == []


def test_daily_bonus_off(fan, settings):
    settings.PREDICTIONS_DAILY_BONUS = 0
    resp = as_user(fan).get("/api/v1/predictions/wallet").json()
    assert (resp["balance"], resp["bonus"]) == (START, 0)
