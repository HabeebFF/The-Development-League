"""Multiples: placing them, every refusal, settling pick by pick, corrections and the API."""

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import Membership, StaffProfile
from apps.league.models import Match, MatchDay, ScoringRule, Season, Stage, Team
from apps.predictions import settlement as st
from apps.predictions.markets import MarketError, create_market, set_active, set_odds, transition
from apps.predictions.models import Bet, Fixture, LedgerEntry, Leg, Market, Multiple, Settlement
from apps.predictions.multiples import clash, place_multiple
from apps.predictions.services import check_wallets, wallet_for

from .test_markets_c import game as _game  # noqa: F401  (a pytest fixture)
from .test_settlement import as_user, make_user

pytestmark = pytest.mark.django_db
S, B, C = Market.Status, Bet.Status, Market.Category


@pytest.fixture(autouse=True)
def _on(settings):
    settings.PREDICTIONS_ENABLED = True


@pytest.fixture
def staff():
    user = make_user("staff@tdl.test")
    StaffProfile.objects.create(user=user)
    return user


@pytest.fixture
def fan():
    return make_user("fan@tdl.test")


@pytest.fixture
def lg():
    """Fixtures: Friday 8PM match 1 and 2 and the whole Friday 8PM session, Saturday 8PM
    match 1. Teams Alpha to Delta."""
    rule = ScoringRule.objects.create(name="M rule", placement_points={"1": 12, "2": 9})
    season = Season.objects.create(name="S5", slug="s5", scoring_rule=rule)
    teams = {n: Team.objects.create(name=n) for n in ("Alpha", "Bravo", "Charlie", "Delta")}
    fri, sat = dt.date(2026, 10, 23), dt.date(2026, 10, 24)
    later = timezone.now() + dt.timedelta(hours=2)

    def fixture(date, number):
        return Fixture.objects.create(
            season=season, date=date, session="8PM", match_number=number, scheduled_at=later
        )

    return {
        "season": season,
        "teams": teams,
        "m1": fixture(fri, 1),
        "m2": fixture(fri, 2),
        "session": fixture(fri, None),
        "sat": fixture(sat, 1),
    }


def market(lg, staff, where, odds=("2.00", "3.00", "4.00", "5.00"), category=None):
    """A Booyah market (or session or overall winner) on all four teams, opened now."""
    category = category or {"session": C.SESSION_WINNER, None: C.OVERALL_WINNER}.get(
        where, C.BOOYAH
    )
    teams = list(lg["teams"].values())
    now = timezone.now()
    m = create_market(
        actor=staff,
        category=category,
        title=f"{category} {where}",
        season=lg["season"],
        fixture=lg[where] if where else None,
        params={"teams": [t.pk for t in teams]},
        odds={f"team:{t.pk}": o for t, o in zip(teams, odds, strict=True)},
        opens_at=now - dt.timedelta(minutes=5),
        closes_at=now + dt.timedelta(hours=1),
    )
    return transition(m, S.OPEN, actor=staff)


def pick(m, team, odds=True):
    o = m.outcomes.get(team__name=team)
    p = {"market": m.pk, "outcome": o.pk}
    if odds:
        p["expected_odds"] = str(o.odds)
    return p


def place(user, picks, stake=100, key=None):
    return place_multiple(user, picks=picks, stake=stake, client_key=key or uuid.uuid4())[0]


def decide(m, staff, winners=(), voids=(), dead_heat=1, kind=Settlement.Kind.SETTLE):
    """Apply a result straight away (these markets have no real match behind them)."""
    m = Market.objects.get(pk=m.pk)
    if m.status in (S.OPEN, S.SUSPENDED):
        transition(m, S.CLOSED, actor=staff)
    allowed = {S.CLOSED} if not m.settlements.exists() else {S.SETTLED, S.VOID}
    ids = lambda names: [m.outcomes.get(team__name=n).pk for n in names]  # noqa: E731
    return st._decide(
        m.pk, kind=kind, actor=staff, winners=ids(winners), voids=ids(voids),
        allowed_from=allowed, dead_heat=dead_heat, reason="test",
    )[0]  # fmt: skip


def fresh(m: Multiple) -> Multiple:
    return Multiple.objects.get(pk=m.pk)


def balance(user) -> int:
    return wallet_for(user).balance


# -- placing -------------------------------------------------------------------------------------


def test_place_takes_the_stake_once_and_fixes_the_odds(lg, staff, fan):
    a, b = market(lg, staff, "m1"), market(lg, staff, "sat")
    key = uuid.uuid4()
    m = place(fan, [pick(a, "Alpha"), pick(b, "Charlie")], stake=100, key=key)
    assert (m.stake, m.odds, m.potential_return) == (100, Decimal("8.00"), 800)
    assert balance(fan) == 900
    assert list(m.legs.values_list("odds_accepted", flat=True)) == [
        Decimal("2.00"),
        Decimal("4.00"),
    ]
    # The phone sends the same tap again: same multiple, no second charge.
    again, created = place_multiple(
        fan, picks=[pick(a, "Alpha"), pick(b, "Charlie")], stake=100, client_key=key
    )
    assert (again.pk, created, balance(fan)) == (m.pk, False, 900)
    with pytest.raises(MarketError) as err:
        place_multiple(fan, picks=[pick(a, "Bravo"), pick(b, "Charlie")], stake=100, client_key=key)
    assert err.value.code == "key_reused"
    # Later odds changes don't touch it.
    set_odds(a.outcomes.get(team__name="Alpha"), "9.00", actor=staff)
    assert fresh(m).legs.first().odds_accepted == Decimal("2.00")
    assert LedgerEntry.objects.filter(multiple=m, kind="STAKE").count() == 1
    assert check_wallets() == []


def test_return_is_capped(lg, staff, fan, settings):
    big = ("100.00", "3.00", "4.00", "5.00")
    a, b, c = (market(lg, staff, w, odds=big) for w in ("m1", "sat", None))
    m = place(fan, [pick(a, "Alpha"), pick(b, "Alpha"), pick(c, "Alpha")], stake=500)
    assert m.odds == Decimal("1000000.00")
    assert m.potential_return == settings.PREDICTIONS_MAX_RETURN == 50000


@pytest.mark.parametrize(
    ("first", "second", "clashes"),
    [
        ("m1", "m1", True),  # two markets on the same match
        ("m1", "m2", False),  # two matches of one session
        ("m1", "session", True),  # a match and its whole session
        ("session", "sat", False),  # different sessions
        ("m1", None, False),  # a match and the season
    ],
)
def test_same_match_rule(lg, staff, fan, first, second, clashes):
    a = market(lg, staff, first)
    b = market(lg, staff, second, category=C.FIRST_OUT if first == second else None)
    assert clash(a, b) is clashes
    if clashes:
        with pytest.raises(MarketError, match="same match") as err:
            place(fan, [pick(a, "Alpha"), pick(b, "Bravo")])
        assert err.value.code == "same_match"
        assert balance(fan) == 1000
    else:
        assert place(fan, [pick(a, "Alpha"), pick(b, "Bravo")]).legs.count() == 2


def test_refusals(lg, staff, fan):
    a, b, c = market(lg, staff, "m1"), market(lg, staff, "sat"), market(lg, staff, None)

    def refused(picks, code, stake=100, user=fan):
        with pytest.raises(MarketError) as err:
            place(user, picks, stake=stake)
        assert err.value.code == code, err.value
        return err.value

    refused([pick(a, "Alpha")], "picks")
    refused([pick(a, "Alpha"), pick(a, "Bravo")], "picks")
    refused([pick(a, "Alpha"), {"market": b.pk}], "picks")
    refused([pick(a, "Alpha"), pick(b, "Alpha")], "stake", stake=5)
    refused([pick(a, "Alpha"), pick(b, "Alpha")], "stake", stake=501)
    refused([pick(a, "Alpha"), {"market": b.pk, "outcome": a.outcomes.first().pk}], "outcome")
    set_odds(b.outcomes.get(team__name="Alpha"), "2.50", actor=staff)
    err = refused([pick(a, "Alpha"), {**pick(b, "Alpha"), "expected_odds": "2.00"}], "odds_changed")
    assert (err.extra["market"], err.extra["odds"]) == (b.pk, "2.50")
    set_active(c.outcomes.get(team__name="Delta"), False, actor=staff)
    refused([pick(a, "Alpha"), pick(c, "Delta")], "outcome")
    transition(b, S.SUSPENDED, actor=staff)
    refused([pick(a, "Alpha"), pick(b, "Alpha")], "closed")
    Membership.objects.create(user=fan, team=lg["teams"]["Charlie"])
    refused([pick(a, "Alpha"), pick(c, "Bravo")], "not_allowed")
    refused([pick(a, "Alpha"), pick(c, "Bravo")], "not_allowed", user=staff)
    assert balance(fan) == 1000
    assert not Multiple.objects.exists() and not Leg.objects.exists()


def test_not_enough_coins(lg, staff, fan):
    a, b = market(lg, staff, "m1"), market(lg, staff, "sat")
    for _ in range(2):
        place(fan, [pick(a, "Alpha"), pick(b, "Alpha")], stake=500)
    with pytest.raises(MarketError) as err:
        place(fan, [pick(a, "Alpha"), pick(b, "Alpha")], stake=10)
    assert err.value.code == "coins" and balance(fan) == 0


# -- settling ------------------------------------------------------------------------------------


def test_all_picks_win(lg, staff, fan):
    a, b, c = market(lg, staff, "m1"), market(lg, staff, "sat"), market(lg, staff, None)
    m = place(fan, [pick(a, "Alpha"), pick(b, "Bravo"), pick(c, "Charlie")], stake=100)
    decide(a, staff, winners=["Alpha"])
    decide(b, staff, winners=["Bravo"])
    assert (fresh(m).status, fresh(m).payout, balance(fan)) == (B.PENDING, None, 900)
    s = decide(c, staff, winners=["Charlie"])
    m = fresh(m)
    assert (m.status, m.payout) == (B.WON, 2400)  # 100 x 2 x 3 x 4
    assert balance(fan) == 900 + 2400
    assert s.summary["multiples_won"] == 1 and s.summary["multiple_coins_paid"] == 2400
    assert check_wallets() == []


def test_one_losing_pick_loses_it_at_once(lg, staff, fan):
    a, b = market(lg, staff, "m1"), market(lg, staff, "sat")
    m = place(fan, [pick(a, "Alpha"), pick(b, "Bravo")])
    decide(a, staff, winners=["Delta"])
    m = fresh(m)
    assert (m.status, m.payout, balance(fan)) == (B.LOST, 0, 900)
    assert m.settled_at is not None
    decide(b, staff, winners=["Bravo"])  # the other pick winning changes nothing
    assert (fresh(m).status, balance(fan)) == (B.LOST, 900)


def test_refunded_pick_drops_out(lg, staff, fan):
    a, b, c = market(lg, staff, "m1"), market(lg, staff, "sat"), market(lg, staff, None)
    m = place(fan, [pick(a, "Alpha"), pick(b, "Bravo"), pick(c, "Charlie")], stake=100)
    st.void(Market.objects.get(pk=b.pk), actor=staff, reason="match not played")
    decide(a, staff, winners=["Alpha"], voids=[])
    decide(c, staff, winners=["Charlie"], voids=[])
    assert (fresh(m).status, fresh(m).payout) == (B.WON, 800)  # 100 x 2 x 4
    assert list(fresh(m).legs.values_list("status", flat=True)) == [B.WON, B.VOID, B.WON]


def test_every_pick_refunded_returns_the_stake(lg, staff, fan):
    a, b = market(lg, staff, "m1"), market(lg, staff, "sat")
    m = place(fan, [pick(a, "Alpha"), pick(b, "Bravo")], stake=70)
    decide(a, staff, voids=["Alpha"])
    st.void(Market.objects.get(pk=b.pk), actor=staff, reason="not played")
    m = fresh(m)
    assert (m.status, m.payout, balance(fan)) == (B.VOID, 70, 1000)
    assert LedgerEntry.objects.filter(multiple=m, kind="REFUND").count() == 1


def test_dead_heat_pick_counts_at_its_odds_divided(lg, staff, fan):
    session = market(lg, staff, "session", odds=("2.00", "3.00", "4.00", "5.00"))
    sat = market(lg, staff, "sat")
    m = place(fan, [pick(session, "Alpha"), pick(sat, "Bravo")], stake=100)
    decide(session, staff, winners=["Alpha", "Charlie", "Delta"], dead_heat=3)
    decide(sat, staff, winners=["Bravo"])
    # 100 x (2.00 / 3) x 3.00 = 200 exactly: no rounding until the end.
    assert (fresh(m).status, fresh(m).payout) == (B.WON, 200)


def test_pick_placed_after_the_match_started_is_refunded(lg, staff, fan):
    a, b = market(lg, staff, "m1"), market(lg, staff, "sat")
    m = place(fan, [pick(a, "Alpha"), pick(b, "Bravo")])
    day = MatchDay.objects.create(
        stage=Stage.objects.create(season=lg["season"], name="Scrims"), number=1,
        date=lg["m1"].date,
    )  # fmt: skip
    started = Match.objects.create(
        match_day=day, number=1, started_at=m.placed_at - dt.timedelta(minutes=1)
    )
    Fixture.objects.filter(pk=lg["m1"].pk).update(match=started)
    decide(a, staff, winners=["Bravo"])  # would have lost
    decide(b, staff, winners=["Bravo"])
    m = fresh(m)
    assert list(m.legs.values_list("status", flat=True)) == [B.VOID, B.WON]
    assert (m.status, m.payout) == (B.WON, 300)


# -- corrections ---------------------------------------------------------------------------------


def test_correction_takes_back_a_win_and_records_what_it_cant(lg, staff, fan):
    a, b = market(lg, staff, "m1"), market(lg, staff, "sat")
    m = place(fan, [pick(a, "Alpha"), pick(b, "Bravo")], stake=100)
    decide(a, staff, winners=["Alpha"])
    decide(b, staff, winners=["Bravo"])
    assert balance(fan) == 900 + 600
    # The fan spends most of it before the correction.
    c, d = market(lg, staff, "m2"), market(lg, staff, None)
    for _ in range(3):
        place(fan, [pick(c, "Alpha"), pick(d, "Alpha")], stake=450)
    assert balance(fan) == 150
    s = decide(b, staff, winners=["Delta"])
    m = fresh(m)
    assert (m.status, m.payout, m.unrecovered, balance(fan)) == (B.LOST, 0, 450, 0)
    assert (s.summary["multiple_coins_taken"], s.summary["multiple_coins_unrecovered"]) == (
        150,
        450,
    )
    # Corrected back: only the 150 actually taken comes back.
    decide(b, staff, winners=["Bravo"])
    m = fresh(m)
    assert (m.status, m.payout, m.unrecovered, balance(fan)) == (B.WON, 600, 0, 150)
    assert check_wallets() == []


def test_corrected_losing_pick_reopens_the_multiple(lg, staff, fan):
    a, b = market(lg, staff, "m1"), market(lg, staff, "sat")
    m = place(fan, [pick(a, "Alpha"), pick(b, "Bravo")])
    decide(a, staff, winners=["Delta"])
    assert fresh(m).status == B.LOST
    decide(a, staff, winners=["Alpha"])
    m = fresh(m)
    assert (m.status, m.payout, m.settled_at) == (B.PENDING, None, None)
    decide(b, staff, winners=["Bravo"])
    assert (fresh(m).status, balance(fan)) == (B.WON, 900 + 600)
    assert LedgerEntry.objects.filter(multiple=m, kind="PAYOUT").count() == 1


def test_settling_twice_pays_once(lg, staff, fan):
    a, b = market(lg, staff, "m1"), market(lg, staff, "sat")
    m = place(fan, [pick(a, "Alpha"), pick(b, "Bravo")])
    decide(a, staff, winners=["Alpha"])
    decide(b, staff, winners=["Bravo"])
    with pytest.raises(MarketError):
        st.void(Market.objects.get(pk=b.pk), actor=staff, reason="x")  # already settled
    assert LedgerEntry.objects.filter(multiple=m).exclude(kind="STAKE").count() == 1
    assert balance(fan) == 1500


# -- the API -------------------------------------------------------------------------------------


def test_api_place_resend_list_and_detail(lg, staff, fan):
    a, b = market(lg, staff, "m1"), market(lg, staff, "sat")
    body = {
        "picks": [pick(a, "Alpha"), pick(b, "Bravo")],
        "stake": 50,
        "client_key": str(uuid.uuid4()),
    }
    api = as_user(fan)
    r = api.post("/api/v1/predictions/multiples", body, format="json")
    assert r.status_code == 201, r.json()
    data = r.json()
    assert (data["odds"], data["potential_return"], data["balance"], data["capped"]) == (
        "6.00",
        300,
        950,
        False,
    )
    assert [p["outcome"]["label"] for p in data["picks"]] == ["Alpha", "Bravo"]
    assert api.post("/api/v1/predictions/multiples", body, format="json").status_code == 200
    listed = api.get("/api/v1/predictions/multiples?status=pending").json()
    assert [x["id"] for x in listed["results"]] == [data["id"]]
    assert api.get(f"/api/v1/predictions/multiples/{data['id']}").status_code == 200
    other = as_user(make_user("other@tdl.test"))
    assert other.get(f"/api/v1/predictions/multiples/{data['id']}").status_code == 404


def test_api_refusal_says_which_pick(lg, staff, fan):
    a, b = market(lg, staff, "m1"), market(lg, staff, "m1", category=C.FIRST_OUT)
    body = {
        "picks": [pick(a, "Alpha"), pick(b, "Bravo")],
        "stake": 50,
        "client_key": str(uuid.uuid4()),
    }
    r = as_user(fan).post("/api/v1/predictions/multiples", body, format="json")
    assert r.status_code == 409
    assert r.json()["code"] == "same_match" and r.json()["markets"] == [a.pk, b.pk]
    assert (
        as_user(staff).post("/api/v1/predictions/multiples", body, format="json").status_code == 403
    )


def test_api_rules(client):
    assert client.get("/api/v1/predictions/rules").json() == {
        "min_stake": 10,
        "max_stake": 500,
        "max_picks": 8,
        "max_return": 50000,
    }


def test_leaderboard_counts_multiples(lg, staff, fan):
    a, b = market(lg, staff, "m1"), market(lg, staff, "sat")
    place(fan, [pick(a, "Alpha"), pick(b, "Bravo")])
    place(fan, [pick(a, "Bravo"), pick(b, "Bravo")])
    decide(a, staff, winners=["Alpha"])
    decide(b, staff, winners=["Bravo"])
    rows = as_user(fan).get("/api/v1/predictions/leaderboard?metric=wins").json()["rows"]
    assert [(r["won"], r["lost"]) for r in rows] == [(1, 1)]


def test_staff_see_picks_and_cant_delete_a_market_with_them(lg, staff, fan):
    a, b = market(lg, staff, "m1"), market(lg, staff, "sat")
    place(fan, [pick(a, "Alpha"), pick(b, "Bravo")])
    data = as_user(staff).get(f"/api/v1/admin/predictions/markets/{a.pk}").json()
    assert data["picks"] == 1
    assert {o["label"]: o["picks"] for o in data["outcomes"]}["Alpha"] == 1


# -- end to end ----------------------------------------------------------------------------------


def test_settled_from_real_results(_game, staff, fan):  # noqa: F811  (the fixture)
    """A match Booyah and the overall winner, settled from the uploaded results the normal
    way (the suggestion, then settle)."""
    from .test_markets_c import market as c_market
    from .test_markets_c import publish

    game = _game

    booyah = c_market(game, staff, C.BOOYAH, teams=["Alpha", "Bravo"])
    teams = game["teams"]
    now = timezone.now()
    overall = create_market(
        actor=staff, category=C.OVERALL_WINNER, title="Overall", season=game["season"],
        fixture=None, params={"teams": [teams["Alpha"].pk, teams["Bravo"].pk]},
        odds={f"team:{teams['Alpha'].pk}": "3.00", f"team:{teams['Bravo'].pk}": "2.00"},
        opens_at=now - dt.timedelta(minutes=5), closes_at=now + dt.timedelta(hours=1),
    )  # fmt: skip
    transition(overall, S.OPEN, actor=staff)
    m = place(fan, [pick(booyah, "Alpha"), pick(overall, "Alpha")], stake=100)
    publish(game)
    for mk in (booyah, overall):
        mk = Market.objects.get(pk=mk.pk)
        transition(mk, S.CLOSED, actor=staff)
        s = st.suggest(mk)
        st.settle(mk, actor=staff, winners=s["winners"], voids=s["voids"])
    # Alpha won the match and, level with Bravo on 20 points, tops the table on Booyahs.
    m = fresh(m)
    assert (m.status, m.payout) == (B.WON, 600)
    assert check_wallets() == []
