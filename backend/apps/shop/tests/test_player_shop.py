"""Player shop: items only league players can buy (with DC), card titles, rating glows,
number and flag, milestone frames, and the extras on the FUT card."""

import datetime as dt

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import StaffProfile, User
from apps.league.models import Match, MatchDay, Player, ScoringRule, Season, Stage, Team
from apps.predictions.services import check_wallet, wallet_for
from apps.results.models import PlayerCard, PlayerMatchResult, TeamMatchResult
from apps.shop import milestones, services
from apps.shop.models import CardDesign, Equipped, OwnedDesign

pytestmark = pytest.mark.django_db
PASSWORD = "a-Long-password-42"
START = 100_000


@pytest.fixture(autouse=True)
def _on(settings):
    settings.PREDICTIONS_ENABLED = True
    settings.PUBLIC_SITE = True
    settings.PREDICTIONS_INITIAL_COINS = START


def make_user(email, name="Someone") -> User:
    return User.objects.create_user(email=email, password=PASSWORD, display_name=name)


def as_user(user) -> APIClient:
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def team():
    return Team.objects.create(name="Alpha")


@pytest.fixture
def pro(team):
    """A fan account linked to league player ACE, who has a weekly card."""
    user = make_user("ace@tdl.test", "Ace")
    player = Player.objects.create(
        game_uid=1, current_name_raw="ACE", display_name="ACE", search_name="ace",
        current_team=team, user=user, country="NG",
    )  # fmt: skip
    PlayerCard.objects.create(
        player=player, week=dt.date(2026, 10, 3), team=team, role="RUSHER", overall=80,
        matches=4, rules="t",
    )  # fmt: skip
    return user


@pytest.fixture
def fan():
    return make_user("fan@tdl.test", "Fan")


@pytest.fixture
def staff():
    user = make_user("staff@tdl.test", "Staff")
    StaffProfile.objects.create(user=user)
    return user


def item(slug) -> CardDesign:
    return CardDesign.objects.get(slug=slug)


def buy(client, slug, **body):
    return client.post(f"/api/v1/shop/designs/{item(slug).pk}/buy", body, format="json")


# -- catalogue ---------------------------------------------------------------------------------


def test_player_items_are_not_in_the_fan_shop():
    fan_slugs = {r["slug"] for r in APIClient().get("/api/v1/shop/designs").json()["designs"]}
    assert "pro-circuit" not in fan_slugs and "title-zone-king" not in fan_slugs
    assert "carbon-black" in fan_slugs


def test_player_shop_prices_run_from_5000_to_10_million():
    data = APIClient().get("/api/v1/shop/player").json()
    assert data["can_buy"] is False and data["player"] is None
    bought = [i["price"] for i in data["items"] if not i["unlock"]]
    assert min(bought) == 5_000 and max(bought) == 10_000_000
    kinds = {i["kind"] for i in data["items"]}
    assert kinds == {"FRAME", "TITLE", "NUMBER", "GLOW"}
    centurion = next(i for i in data["items"] if i["slug"] == "centurion")
    assert centurion["unlock"]["label"] == "Reach 100 kills"


def test_player_shop_is_on_its_own_address_not_under_predictions():
    from django.urls import reverse

    assert reverse("shop-player") == "/api/v1/shop/player"


# -- who can buy -------------------------------------------------------------------------------


def test_a_league_player_buys_with_dc(pro):
    resp = buy(as_user(pro), "pro-circuit", equip=True)
    assert resp.status_code == 201, resp.content
    assert resp.json()["balance"] == START - 5_000
    assert Equipped.objects.get(user=pro).design == item("pro-circuit")
    check_wallet(wallet_for(pro))


def test_a_fan_cant_buy_player_items(fan):
    resp = buy(as_user(fan), "pro-circuit")
    assert resp.status_code == 400
    assert "league players" in resp.json()["detail"]
    assert wallet_for(fan).balance == START


def test_staff_cant_buy_player_items(staff, team):
    Player.objects.create(
        game_uid=9, current_name_raw="BOSS", display_name="BOSS", search_name="boss",
        current_team=team, user=staff,
    )  # fmt: skip
    assert buy(as_user(staff), "pro-circuit").status_code == 403


def test_signed_out_visitors_can_look_but_not_buy():
    assert APIClient().get("/api/v1/shop/player").status_code == 200
    assert buy(APIClient(), "pro-circuit").status_code in (401, 403)


def test_cant_buy_twice_or_go_below_zero(pro):
    c = as_user(pro)
    assert buy(c, "night-ops").status_code == 201
    assert buy(c, "night-ops").status_code == 400
    resp = buy(c, "apex")  # 10,000,000 DC
    assert resp.status_code == 400
    assert not OwnedDesign.objects.filter(user=pro, design=item("apex")).exists()
    check_wallet(wallet_for(pro))


def test_milestone_frames_cant_be_bought(pro):
    resp = buy(as_user(pro), "centurion")
    assert resp.status_code == 400
    assert "milestone" in resp.json()["detail"]


def test_the_player_shop_page_shows_my_balance_and_owned_items(pro):
    services.buy(pro, item("title-nade-god").pk)
    data = as_user(pro).get("/api/v1/shop/player").json()
    assert data["can_buy"] is True
    assert data["player"]["name"] == "ACE"
    assert data["balance"] == START - 5_000
    nade = next(i for i in data["items"] if i["slug"] == "title-nade-god")
    assert nade["owned"] is True and nade["equipped"] is False


# -- equipping extras ---------------------------------------------------------------------------


def test_title_glow_and_frame_each_have_their_own_slot(pro):
    c = as_user(pro)
    for slug in ("title-zone-king", "glow-gold", "pro-circuit"):
        assert buy(c, slug).status_code == 201
    for kind, slug in (
        ("TITLE", "title-zone-king"),
        ("GLOW", "glow-gold"),
        ("FRAME", "pro-circuit"),
    ):
        resp = c.post(
            "/api/v1/shop/player/equip", {"kind": kind, "design": item(slug).pk}, format="json"
        )  # noqa: E501
        assert resp.status_code == 200, resp.content
    eq = Equipped.objects.get(user=pro)
    assert (eq.title.slug, eq.glow.slug, eq.design.slug) == (
        "title-zone-king",
        "glow-gold",
        "pro-circuit",
    )  # noqa: E501
    # A title can't go in the glow slot.
    resp = c.post(
        "/api/v1/shop/player/equip", {"kind": "GLOW", "design": item("title-zone-king").pk},
        format="json",
    )  # fmt: skip
    assert resp.status_code == 400
    # Taking the title off.
    c.post("/api/v1/shop/player/equip", {"kind": "TITLE", "design": None}, format="json")
    assert Equipped.objects.get(user=pro).title is None


def test_cant_equip_what_you_dont_own(pro):
    resp = as_user(pro).post(
        "/api/v1/shop/player/equip", {"kind": "TITLE", "design": item("title-zone-king").pk},
        format="json",
    )  # fmt: skip
    assert resp.status_code == 400


def test_number_and_flag_need_the_item(pro):
    c = as_user(pro)
    url = "/api/v1/shop/player/number"
    assert c.post(url, {"number": 7, "flag": "ng"}, format="json").status_code == 400
    buy(c, "number-and-flag")
    resp = c.post(url, {"number": 7, "flag": "ng"}, format="json")
    assert resp.json() == {"number": 7, "flag": "NG"}
    assert c.post(url, {"number": 100, "flag": "NG"}, format="json").status_code == 400
    assert c.post(url, {"number": 7, "flag": "NGA"}, format="json").status_code == 400


def test_extras_show_on_the_weekly_card_and_not_on_specials(pro):
    c = as_user(pro)
    for slug in ("title-zone-king", "glow-cyan", "number-and-flag"):
        buy(c, slug, equip=True)
    c.post("/api/v1/shop/player/number", {"number": 10, "flag": "NG"}, format="json")
    cards = APIClient().get("/api/v1/cards?week=2026-10-03").json()["cards"]
    extras = cards[0]["extras"]
    assert extras["title"] == "Zone King"
    assert extras["glow"] == "cyan"
    assert (extras["number"], extras["flag"]) == (10, "NG")
    from apps.league import views

    assert open(views.__file__).read().count('"extras": None') >= 4


def test_refund_takes_extras_off_the_card(pro, staff):
    c = as_user(pro)
    buy(c, "title-rush-lord", equip=True)
    buy(c, "number-and-flag")
    c.post("/api/v1/shop/player/number", {"number": 9, "flag": "NG"}, format="json")
    for o in OwnedDesign.objects.filter(user=pro):
        services.refund(o.pk, staff)
    eq = Equipped.objects.get(user=pro)
    assert eq.title is None and eq.shirt_number is None and eq.flag == ""
    assert wallet_for(pro).balance == START
    check_wallet(wallet_for(pro))


def test_staff_can_only_gift_player_items_to_players(fan, pro, staff):
    with pytest.raises(services.ShopError):
        services.gift(fan, item("booyah-gold").pk, staff)
    assert services.gift(pro, item("booyah-gold").pk, staff).price_paid == 0


# -- milestones --------------------------------------------------------------------------------


def _played(player, team, kills, placement, n):
    rule, _ = ScoringRule.objects.get_or_create(name="R", defaults={"placement_points": {}})
    season, _ = Season.objects.get_or_create(name="S", slug="s", defaults={"scoring_rule": rule})
    stage, _ = Stage.objects.get_or_create(season=season, name="Scrims")
    day, _ = MatchDay.objects.get_or_create(stage=stage, number=1, defaults={"title": "D1"})
    match = Match.objects.create(match_day=day, number=n, status=Match.Status.PUBLISHED)
    TeamMatchResult.objects.create(
        match=match, team=team, in_game_name="A", placement=placement, kills=kills,
        placement_points=0, kill_points=kills, total_points=kills,
    )  # fmt: skip
    PlayerMatchResult.objects.create(
        match=match, player=player, team=team, raw_name="ACE", display_name="ACE", kills=kills
    )


def test_progress_counts_kills_booyahs_and_totw(pro, team):
    player = Player.objects.get(user=pro)
    _played(player, team, 60, 1, 1)
    _played(player, team, 45, 3, 2)
    PlayerCard.objects.filter(player=player).update(totw=["MVP"])
    assert milestones.progress(player) == {"kills": 105, "booyahs": 1, "totw": 1}


def test_opening_the_shop_hands_out_reached_milestones_once(pro, team):
    player = Player.objects.get(user=pro)
    _played(player, team, 99, 2, 1)
    c = as_user(pro)
    data = c.get("/api/v1/shop/player").json()
    centurion = next(i for i in data["items"] if i["slug"] == "centurion")
    assert centurion["owned"] is False and centurion["unlock"]["progress"] == 99
    _played(player, team, 1, 2, 2)
    data = c.get("/api/v1/shop/player").json()
    centurion = next(i for i in data["items"] if i["slug"] == "centurion")
    assert centurion["owned"] is True
    c.get("/api/v1/shop/player")
    assert OwnedDesign.objects.filter(user=pro, design__slug="centurion").count() == 1
    assert wallet_for(pro).balance == START  # free
    resp = c.post(
        "/api/v1/shop/player/equip", {"kind": "FRAME", "design": item("centurion").pk},
        format="json",
    )  # fmt: skip
    assert resp.status_code == 200


# -- staff -------------------------------------------------------------------------------------


def test_staff_add_a_player_title(staff):
    c = as_user(staff)
    body = {
        "slug": "title-iron-wall", "name": "Iron Wall", "kind": "TITLE", "players_only": True,
        "rarity": "RARE", "price": 7000,
        "parts": {"palette": "carbon", "pattern": "none", "effect": "none"},
    }  # fmt: skip
    assert c.post("/api/v1/admin/shop/designs", body, format="json").status_code == 201
    # Titles must be in the Player shop, and milestones need a valid rule.
    bad = {**body, "slug": "x1", "players_only": False}
    assert c.post("/api/v1/admin/shop/designs", bad, format="json").status_code == 400
    bad = {**body, "slug": "x2", "kind": "FRAME", "unlock": "wins:3", "price": 0}
    assert c.post("/api/v1/admin/shop/designs", bad, format="json").status_code == 400
    ok = {**body, "slug": "x3", "kind": "FRAME", "unlock": "kills:500", "price": 0}
    assert c.post("/api/v1/admin/shop/designs", ok, format="json").status_code == 201
