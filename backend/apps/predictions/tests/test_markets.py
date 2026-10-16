"""Markets and bets: who can create and change them, status rules, odds, and placing bets."""

import datetime as dt
import threading
import uuid
from decimal import Decimal

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Membership, StaffProfile, User
from apps.league.models import ScoringRule, Season, Team
from apps.predictions.markets import (
    MarketError,
    close_due_markets,
    create_market,
    place_bet,
    potential_return,
    transition,
)
from apps.predictions.models import Bet, Fixture, LedgerEntry, Market, MarketEvent, OddsChange
from apps.predictions.services import check_wallets, wallet_for

pytestmark = pytest.mark.django_db
S = Market.Status
PASSWORD = "a-Long-password-42"


@pytest.fixture(autouse=True)
def _on(settings):
    settings.PREDICTIONS_ENABLED = True


def make_user(email: str, **extra) -> User:
    return User.objects.create_user(email=email, password=PASSWORD, **extra)


def as_user(user: User | None) -> APIClient:
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


@pytest.fixture
def staff() -> User:
    user = make_user("staff@tdl.test")
    StaffProfile.objects.create(user=user)
    return user


@pytest.fixture
def fan() -> User:
    return make_user("fan@tdl.test", display_name="Fan")


@pytest.fixture
def league():
    rule, _ = ScoringRule.objects.get_or_create(name="Test rule", defaults={"placement_points": {}})
    season = Season.objects.create(name="S1", slug="s1", scoring_rule=rule)
    teams = [Team.objects.create(name=n) for n in ("Alpha", "Bravo", "Charlie")]
    fixture = Fixture.objects.create(
        season=season,
        date=dt.date(2026, 10, 16),
        session="8PM",
        match_number=1,
        scheduled_at=timezone.now() + dt.timedelta(hours=2),
    )
    return season, teams, fixture


def booyah(league, staff, *, status=S.OPEN, odds=("2.50", "3.00", "4.00"), **times) -> Market:
    season, teams, fixture = league
    now = timezone.now()
    market = create_market(
        actor=staff,
        category=Market.Category.BOOYAH,
        title="Booyah, Match 1",
        season=season,
        fixture=fixture,
        params={"teams": [t.pk for t in teams]},
        odds={f"team:{t.pk}": o for t, o in zip(teams, odds, strict=True)},
        opens_at=times.get("opens_at", now - dt.timedelta(minutes=5)),
        closes_at=times.get("closes_at", now + dt.timedelta(hours=1)),
    )
    if status != S.DRAFT:
        transition(market, S.OPEN, actor=staff)
    if status not in (S.DRAFT, S.OPEN):
        transition(market, status, actor=staff)
    market.refresh_from_db()
    return market


def bet(user, market, *, n: int = 0, stake=100, key=None, **extra):
    outcome = market.outcomes.order_by("sort")[n]
    return place_bet(
        user,
        market_id=market.pk,
        outcome_id=outcome.pk,
        stake=stake,
        client_key=key or uuid.uuid4(),
        **extra,
    )


def balance(user) -> int:
    return wallet_for(user).balance


# -- placing a bet -------------------------------------------------------------------------------


def test_valid_bet_deducts_stake_and_records_everything(league, staff, fan):
    market = booyah(league, staff)
    placed, created = bet(fan, market, stake=100)
    assert created
    assert placed.odds_accepted == Decimal("2.50") and placed.potential_return == 250
    assert placed.status == Bet.Status.PENDING and placed.payout is None
    assert balance(fan) == 900
    entry = LedgerEntry.objects.get(bet=placed)
    assert (entry.kind, entry.amount, entry.balance_after) == ("STAKE", -100, 900)


def test_bet_through_api_shows_return_profit_and_balance(league, staff, fan):
    market = booyah(league, staff)
    outcome = market.outcomes.order_by("sort")[0]
    body = {
        "market": market.pk,
        "outcome": outcome.pk,
        "stake": 100,
        "client_key": str(uuid.uuid4()),
    }
    resp = as_user(fan).post("/api/v1/predictions/bets", body, format="json")
    assert resp.status_code == 201, resp.content
    data = resp.json()
    assert data["odds_accepted"] == "2.50"
    assert (data["potential_return"], data["potential_profit"], data["balance"]) == (250, 150, 900)
    mine = as_user(fan).get("/api/v1/predictions/bets?status=pending").json()
    assert [b["id"] for b in mine["results"]] == [data["id"]]


def test_client_cannot_choose_the_odds(league, staff, fan):
    market = booyah(league, staff)
    outcome = market.outcomes.order_by("sort")[0]
    body = {
        "market": market.pk,
        "outcome": outcome.pk,
        "stake": 100,
        "client_key": str(uuid.uuid4()),
        "odds": "900.00",
        "odds_accepted": "900.00",
        "potential_return": 90000,
    }
    resp = as_user(fan).post("/api/v1/predictions/bets", body, format="json")
    assert resp.status_code == 201
    assert resp.json()["odds_accepted"] == "2.50" and resp.json()["potential_return"] == 250


def test_return_is_rounded_down_to_whole_coins():
    assert potential_return(33, Decimal("1.55")) == 51  # 51.15
    assert potential_return(10, Decimal("1.01")) == 10  # 10.1
    assert potential_return(500, Decimal("1000.00")) == 500000


@pytest.mark.parametrize(
    "change",
    [
        {"stake": 5},
        {"stake": 501},
        {"stake": 0},
        {"stake": -50},
        {"stake": 10.5},
        {"stake": True},
        {"outcome": "other-market"},
        {"outcome": 999999},
        {"market": 999999},
    ],
)
def test_invalid_bet_takes_no_coins(league, staff, fan, change):
    market = booyah(league, staff)
    other = booyah(league, staff)
    outcome_id = market.outcomes.first().pk
    if change.get("outcome") == "other-market":
        outcome_id = other.outcomes.first().pk
    elif "outcome" in change:
        outcome_id = change["outcome"]
    with pytest.raises(MarketError):
        place_bet(
            fan,
            market_id=change.get("market", market.pk),
            outcome_id=outcome_id,
            stake=change.get("stake", 100),
            client_key=uuid.uuid4(),
        )
    assert balance(fan) == 1000
    assert not Bet.objects.exists()
    assert not LedgerEntry.objects.filter(kind="STAKE").exists()


def test_api_rejects_bad_stake_and_ids_without_charging(league, staff, fan):
    market = booyah(league, staff)
    client = as_user(fan)
    key = str(uuid.uuid4())
    for body in (
        {
            "market": market.pk,
            "outcome": market.outcomes.first().pk,
            "stake": "lots",
            "client_key": key,
        },
        {"market": market.pk, "outcome": "abc", "stake": 100, "client_key": key},
        {
            "market": market.pk,
            "outcome": market.outcomes.first().pk,
            "stake": 100,
            "client_key": "x",
        },
    ):
        assert client.post("/api/v1/predictions/bets", body, format="json").status_code == 400
    assert balance(fan) == 1000


def test_cannot_stake_more_than_balance(league, staff, fan):
    market = booyah(league, staff)
    for _ in range(2):
        bet(fan, market, stake=500)
    assert balance(fan) == 0
    with pytest.raises(MarketError, match="Not enough coins"):
        bet(fan, market, stake=10)
    assert Bet.objects.filter(user=fan).count() == 2


@pytest.mark.parametrize("status", [S.DRAFT, S.SUSPENDED, S.CLOSED])
def test_no_bets_unless_market_is_open(league, staff, fan, status):
    market = booyah(league, staff, status=status)
    with pytest.raises(MarketError):
        bet(fan, market)
    assert balance(fan) == 1000


def test_no_bets_after_closing_time_even_if_still_marked_open(league, staff, fan):
    market = booyah(league, staff)
    Market.objects.filter(pk=market.pk).update(closes_at=timezone.now() - dt.timedelta(seconds=1))
    market.refresh_from_db()
    assert market.status == S.OPEN
    with pytest.raises(MarketError, match="isn't taking"):
        bet(fan, market)
    outcome = market.outcomes.first()
    resp = as_user(fan).post(
        "/api/v1/predictions/bets",
        {"market": market.pk, "outcome": outcome.pk, "stake": 50, "client_key": str(uuid.uuid4())},
        format="json",
    )
    assert resp.status_code == 400 and resp.json()["code"] == "closed"
    assert balance(fan) == 1000


def test_no_bets_before_opening_time(league, staff, fan):
    now = timezone.now()
    market = booyah(
        league,
        staff,
        opens_at=now + dt.timedelta(minutes=10),
        closes_at=now + dt.timedelta(hours=1),
    )
    with pytest.raises(MarketError):
        bet(fan, market)


def test_switched_off_choice_takes_no_bets(league, staff, fan):
    market = booyah(league, staff)
    outcome = market.outcomes.order_by("sort")[0]
    resp = as_user(staff).patch(
        f"/api/v1/admin/predictions/outcomes/{outcome.pk}", {"is_active": False}, format="json"
    )
    assert resp.status_code == 200, resp.content
    with pytest.raises(MarketError, match="no longer available"):
        bet(fan, market, n=0)


def test_accepted_odds_never_change_afterwards(league, staff, fan):
    market = booyah(league, staff)
    placed, _ = bet(fan, market, stake=100)
    outcome = placed.outcome
    resp = as_user(staff).patch(
        f"/api/v1/admin/predictions/outcomes/{outcome.pk}", {"odds": "1.20"}, format="json"
    )
    assert resp.status_code == 200, resp.content
    placed.refresh_from_db()
    assert placed.odds_accepted == Decimal("2.50") and placed.potential_return == 250
    later, _ = bet(fan, market, stake=100)
    assert later.odds_accepted == Decimal("1.20") and later.potential_return == 120
    change = OddsChange.objects.get(outcome=outcome)
    assert (change.old, change.new, change.by) == (Decimal("2.50"), Decimal("1.20"), staff)


def test_odds_changed_since_the_slip_was_shown(league, staff, fan):
    market = booyah(league, staff)
    outcome = market.outcomes.order_by("sort")[0]
    as_user(staff).patch(
        f"/api/v1/admin/predictions/outcomes/{outcome.pk}", {"odds": "2.10"}, format="json"
    )
    body = {
        "market": market.pk,
        "outcome": outcome.pk,
        "stake": 100,
        "client_key": str(uuid.uuid4()),
        "expected_odds": "2.50",
    }
    resp = as_user(fan).post("/api/v1/predictions/bets", body, format="json")
    assert resp.status_code == 409 and resp.json()["odds"] == "2.10"
    assert balance(fan) == 1000


# -- duplicates and two taps at once -------------------------------------------------------------


def test_same_confirmation_twice_is_one_bet(league, staff, fan):
    market = booyah(league, staff)
    key = uuid.uuid4()
    first, created = bet(fan, market, key=key)
    again, created_again = bet(fan, market, key=key)
    assert created and not created_again and again.pk == first.pk
    assert balance(fan) == 900


def test_same_confirmation_for_a_different_bet_is_refused(league, staff, fan):
    market = booyah(league, staff)
    key = uuid.uuid4()
    bet(fan, market, key=key, stake=100)
    with pytest.raises(MarketError) as exc:
        bet(fan, market, key=key, stake=200)
    assert exc.value.code == "key_reused"
    assert balance(fan) == 900


def _at_once(n: int, work) -> list:
    barrier = threading.Barrier(n)
    results: list = [None] * n

    def run(i):
        try:
            barrier.wait()
            results[i] = work(i)
        except Exception as exc:  # noqa: BLE001
            results[i] = exc
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


@pytest.mark.django_db(transaction=True)
def test_simultaneous_bets_cannot_overspend(league, staff, fan):
    market = booyah(league, staff)
    wallet_for(fan)
    results = _at_once(8, lambda i: bet(fan, market, stake=300))
    ok = [r for r in results if isinstance(r, tuple)]
    assert len(ok) == 3, results
    assert balance(fan) == 100
    assert Bet.objects.filter(user=fan).count() == 3
    assert check_wallets() == []


@pytest.mark.django_db(transaction=True)
def test_simultaneous_double_tap_is_one_bet(league, staff, fan):
    market = booyah(league, staff)
    wallet_for(fan)
    key = uuid.uuid4()
    results = _at_once(6, lambda i: bet(fan, market, key=key))
    assert all(isinstance(r, tuple) for r in results), results
    assert len({r[0].pk for r in results}) == 1
    assert balance(fan) == 900
    assert check_wallets() == []


# -- who may bet ---------------------------------------------------------------------------------


def test_staff_cannot_bet(league, staff):
    market = booyah(league, staff)
    with pytest.raises(MarketError) as exc:
        bet(staff, market)
    assert exc.value.code == "not_allowed"


def test_player_cannot_bet_on_own_team(league, staff):
    _, teams, _ = league
    player = make_user("player@tdl.test")
    Membership.objects.create(user=player, team=teams[1])
    market = booyah(league, staff)
    with pytest.raises(MarketError, match="your team"):
        bet(player, market)
    assert balance(player) == 1000


def test_signed_out_visitors_cannot_bet(league, staff):
    market = booyah(league, staff)
    resp = as_user(None).post(
        "/api/v1/predictions/bets",
        {
            "market": market.pk,
            "outcome": market.outcomes.first().pk,
            "stake": 10,
            "client_key": str(uuid.uuid4()),
        },
        format="json",
    )
    assert resp.status_code in (401, 403)


def test_users_cannot_see_other_peoples_bets(league, staff, fan):
    market = booyah(league, staff)
    other = make_user("other@tdl.test")
    theirs, _ = bet(other, market)
    assert as_user(fan).get(f"/api/v1/predictions/bets/{theirs.pk}").status_code == 404
    assert as_user(fan).get("/api/v1/predictions/bets").json()["count"] == 0
    assert (
        as_user(fan).get(f"/api/v1/admin/predictions/markets/{market.pk}/bets").status_code == 403
    )


# -- staff only ----------------------------------------------------------------------------------


def _create_body(league, **extra):
    season, teams, fixture = league
    now = timezone.now()
    return {
        "title": "Head-to-head: Alpha v Bravo",
        "category": "H2H_PLACEMENT",
        "season": season.pk,
        "fixture": fixture.pk,
        "params": {"teams": [teams[0].pk, teams[1].pk]},
        "odds": {f"team:{teams[0].pk}": "1.80", f"team:{teams[1].pk}": "2.00"},
        "opens_at": (now - dt.timedelta(minutes=1)).isoformat(),
        "closes_at": (now + dt.timedelta(hours=1)).isoformat(),
    } | extra


def test_only_staff_create_markets_change_odds_or_status(league, staff, fan):
    body = _create_body(league)
    assert (
        as_user(fan).post("/api/v1/admin/predictions/markets", body, format="json").status_code
        == 403
    )
    resp = as_user(staff).post("/api/v1/admin/predictions/markets", body, format="json")
    assert resp.status_code == 201, resp.content
    market = resp.json()
    assert market["status"] == "DRAFT" and len(market["outcomes"]) == 2
    outcome = market["outcomes"][0]["id"]
    url = f"/api/v1/admin/predictions/outcomes/{outcome}"
    assert as_user(fan).patch(url, {"odds": "50.00"}, format="json").status_code == 403
    t_url = f"/api/v1/admin/predictions/markets/{market['id']}/transition"
    assert as_user(fan).post(t_url, {"to": "OPEN"}, format="json").status_code == 403
    assert as_user(staff).post(t_url, {"to": "OPEN"}, format="json").status_code == 200


@pytest.mark.parametrize(
    "odds", ["0", "-2.00", "1.00", "1000.01", "2.555", "abc", "NaN", "Infinity"]
)
def test_invalid_odds_are_refused(league, staff, odds):
    _, teams, _ = league
    body = _create_body(league, odds={f"team:{teams[0].pk}": odds, f"team:{teams[1].pk}": "2.00"})
    resp = as_user(staff).post("/api/v1/admin/predictions/markets", body, format="json")
    assert resp.status_code == 400, resp.content
    assert not Market.objects.exists()


def test_invalid_odds_change_is_refused(league, staff):
    market = booyah(league, staff)
    outcome = market.outcomes.first()
    for odds in ("0", "-1", "1.00", "abc"):
        resp = as_user(staff).patch(
            f"/api/v1/admin/predictions/outcomes/{outcome.pk}", {"odds": odds}, format="json"
        )
        assert resp.status_code == 400
    outcome.refresh_from_db()
    assert outcome.odds == Decimal("2.50")


def test_market_needs_odds_for_every_outcome_and_valid_params(league, staff):
    _, teams, _ = league
    client = as_user(staff)
    missing = _create_body(league, odds={f"team:{teams[0].pk}": "1.80"})
    assert (
        client.post("/api/v1/admin/predictions/markets", missing, format="json").status_code == 400
    )
    three = _create_body(league, params={"teams": [t.pk for t in teams]})
    assert client.post("/api/v1/admin/predictions/markets", three, format="json").status_code == 400
    window = _create_body(
        league,
        closes_at=timezone.now().isoformat(),
        opens_at=(timezone.now() + dt.timedelta(hours=1)).isoformat(),
    )
    assert (
        client.post("/api/v1/admin/predictions/markets", window, format="json").status_code == 400
    )


def test_top_n_market_has_yes_and_no(league, staff):
    season, teams, fixture = league
    market = create_market(
        actor=staff,
        category=Market.Category.TOP_N,
        title="Alpha top 3",
        season=season,
        fixture=fixture,
        params={"team": teams[0].pk, "n": 3},
        odds={"yes": "1.90", "no": "1.90"},
        opens_at=timezone.now(),
        closes_at=timezone.now() + dt.timedelta(hours=1),
    )
    assert [o.code for o in market.outcomes.order_by("sort")] == ["yes", "no"]
    with pytest.raises(MarketError):
        create_market(
            actor=staff,
            category=Market.Category.TOP_N,
            title="Top 4?",
            season=season,
            params={"team": teams[0].pk, "n": 4},
            odds={"yes": "1.90", "no": "1.90"},
            opens_at=timezone.now(),
            closes_at=timezone.now() + dt.timedelta(hours=1),
        )


# -- status rules --------------------------------------------------------------------------------


def test_allowed_and_refused_status_changes(league, staff):
    market = booyah(league, staff, status=S.DRAFT)
    with pytest.raises(MarketError):
        transition(market, S.CLOSED, actor=staff)  # draft can only open or be voided
    transition(market, S.OPEN, actor=staff)
    transition(market, S.SUSPENDED, actor=staff, reason="Lobby delayed")
    transition(market, S.OPEN, actor=staff)
    transition(market, S.CLOSED, actor=staff)
    with pytest.raises(MarketError):
        transition(market, S.SUSPENDED, actor=staff)
    with pytest.raises(MarketError, match="settle or void"):
        transition(market, S.SETTLED, actor=staff)
    steps = list(market.events.order_by("pk").values_list("from_status", "to_status"))
    assert steps == [
        ("", "DRAFT"),
        ("DRAFT", "OPEN"),
        ("OPEN", "SUSPENDED"),
        ("SUSPENDED", "OPEN"),
        ("OPEN", "CLOSED"),
    ]
    assert MarketEvent.objects.get(to_status="SUSPENDED").reason == "Lobby delayed"


def test_cannot_reopen_after_closing_time(league, staff):
    market = booyah(league, staff, status=S.CLOSED)
    Market.objects.filter(pk=market.pk).update(closes_at=timezone.now() - dt.timedelta(minutes=1))
    with pytest.raises(MarketError, match="move it later"):
        transition(market, S.OPEN, actor=staff)


def test_due_markets_are_closed_by_the_minute_job(league, staff):
    market = booyah(league, staff)
    Market.objects.filter(pk=market.pk).update(closes_at=timezone.now() - dt.timedelta(seconds=1))
    assert close_due_markets() == 1
    market.refresh_from_db()
    assert market.status == S.CLOSED
    assert market.events.latest("pk").reason == "Closing time reached"


def test_public_lists_hide_drafts_and_show_closed_by_time(league, staff, fan):
    draft = booyah(league, staff, status=S.DRAFT)
    open_ = booyah(league, staff)
    past = booyah(league, staff)
    Market.objects.filter(pk=past.pk).update(closes_at=timezone.now() - dt.timedelta(seconds=1))
    client = as_user(fan)
    open_ids = [m["id"] for m in client.get("/api/v1/predictions/markets").json()["results"]]
    assert open_ids == [open_.pk]
    closed = client.get("/api/v1/predictions/markets?status=closed").json()["results"]
    assert [(m["id"], m["status"], m["accepting"]) for m in closed] == [(past.pk, "CLOSED", False)]
    assert client.get(f"/api/v1/predictions/markets/{draft.pk}").status_code == 404


def test_predictions_hidden_when_switched_off(league, staff, fan, settings):
    booyah(league, staff)
    settings.PREDICTIONS_ENABLED = False
    assert as_user(fan).get("/api/v1/predictions/markets").status_code == 404
    assert as_user(fan).get("/api/v1/predictions/bets").status_code == 404


def test_settled_or_void_markets_cannot_be_edited_and_drafts_with_bets_are_kept(league, staff, fan):
    market = booyah(league, staff)
    bet(fan, market)
    client = as_user(staff)
    assert client.delete(f"/api/v1/admin/predictions/markets/{market.pk}").status_code == 400
    Market.objects.filter(pk=market.pk).update(status=S.VOID)
    resp = client.patch(
        f"/api/v1/admin/predictions/markets/{market.pk}", {"title": "New"}, format="json"
    )
    assert resp.status_code == 400
    outcome = market.outcomes.first()
    resp = client.patch(
        f"/api/v1/admin/predictions/outcomes/{outcome.pk}", {"odds": "3.00"}, format="json"
    )
    assert resp.status_code == 400


def test_staff_see_bets_totals_and_history(league, staff, fan):
    market = booyah(league, staff)
    bet(fan, market, stake=100)
    as_user(staff).patch(
        f"/api/v1/admin/predictions/outcomes/{market.outcomes.order_by('sort')[1].pk}",
        {"odds": "3.50"},
        format="json",
    )
    client = as_user(staff)
    detail = client.get(f"/api/v1/admin/predictions/markets/{market.pk}").json()
    assert detail["bets"] == 1 and detail["outcomes"][0]["staked"] == 100
    bets = client.get(f"/api/v1/admin/predictions/markets/{market.pk}/bets").json()
    assert bets["results"][0]["user"]["email"] == "fan@tdl.test"
    history = client.get(f"/api/v1/admin/predictions/markets/{market.pk}/history").json()
    assert {h["type"] for h in history} == {"status", "odds"}


def test_fixtures_are_staff_only_and_unique(league, staff, fan):
    season, _, _ = league
    body = {
        "season": season.pk,
        "date": "2026-10-16",
        "session": "8PM",
        "match_number": 1,
        "scheduled_at": "2026-10-16T19:00:00Z",
    }
    assert (
        as_user(fan).post("/api/v1/admin/predictions/fixtures", body, format="json").status_code
        == 403
    )
    dup = as_user(staff).post("/api/v1/admin/predictions/fixtures", body, format="json")
    assert dup.status_code == 400
    session = as_user(staff).post(
        "/api/v1/admin/predictions/fixtures", body | {"match_number": None}, format="json"
    )
    assert session.status_code == 201, session.content
    again = as_user(staff).post(
        "/api/v1/admin/predictions/fixtures", body | {"match_number": None}, format="json"
    )
    assert again.status_code == 400
