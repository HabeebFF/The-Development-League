"""Settling, voiding and correcting markets, and the whole life of a bet through the API."""

import datetime as dt
import threading
import uuid

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import StaffProfile, User
from apps.league.models import Match, MatchDay, ScoringRule, Season, Stage, Team
from apps.predictions.markets import MarketError, create_market, place_bet, transition
from apps.predictions.models import Bet, Fixture, LedgerEntry, Market, Settlement
from apps.predictions.services import check_wallets, wallet_for
from apps.predictions.settlement import correct, settle, suggest, void
from apps.results.models import TeamMatchResult

pytestmark = pytest.mark.django_db
S, B, C = Market.Status, Bet.Status, Market.Category
PASSWORD = "a-Long-password-42"


@pytest.fixture(autouse=True)
def _on(settings):
    settings.PREDICTIONS_ENABLED = True


def make_user(email: str) -> User:
    return User.objects.create_user(email=email, password=PASSWORD, display_name=email[:5])


def as_user(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def staff() -> User:
    user = make_user("staff@tdl.test")
    StaffProfile.objects.create(user=user)
    return user


@pytest.fixture
def fans():
    return [make_user(f"fan{i}@tdl.test") for i in range(3)]


@pytest.fixture
def league():
    """Alpha wins (5 kills, 17 pts), Bravo 2nd (8 kills, 17 pts), Charlie 3rd (5 kills, 8 pts).
    Delta is in the season but doesn't play this match."""
    rule, _ = ScoringRule.objects.get_or_create(name="Test rule", defaults={"placement_points": {}})
    season = Season.objects.create(name="S1", slug="s1", scoring_rule=rule)
    stage = Stage.objects.create(season=season, name="Scrims")
    day = MatchDay.objects.create(stage=stage, number=1, date=dt.date(2026, 10, 16))
    match = Match.objects.create(match_day=day, number=1, status=Match.Status.PROCESSING)
    teams = {n: Team.objects.create(name=n) for n in ("Alpha", "Bravo", "Charlie", "Delta")}
    for name, place, kills, pts in (("Alpha", 1, 5, 17), ("Bravo", 2, 8, 17), ("Charlie", 3, 5, 8)):
        TeamMatchResult.objects.create(
            match=match, team=teams[name], in_game_name=name, placement=place, kills=kills,
            placement_points=pts - kills, kill_points=kills, total_points=pts,
        )  # fmt: skip
    fixture = Fixture.objects.create(
        season=season,
        date=day.date,
        session="8PM",
        match_number=1,
        scheduled_at=timezone.now() + dt.timedelta(hours=1),
    )
    return {"season": season, "match": match, "teams": teams, "fixture": fixture}


def make_market(league, staff, category=C.BOOYAH, teams=("Alpha", "Bravo", "Charlie"), **kw):
    ids = [league["teams"][t].pk for t in teams]
    if category == C.TOP_N:
        params, odds = {"team": ids[0], "n": kw.pop("n", 3)}, {"yes": "1.50", "no": "2.50"}
    else:
        params = {"teams": ids}
        odds = {f"team:{t}": o for t, o in zip(ids, ("2.50", "3.00", "4.00", "6.00"), strict=False)}
    now = timezone.now()
    market = create_market(
        actor=staff,
        category=category,
        title=f"{category} market",
        season=league["season"],
        fixture=league["fixture"],
        params=params,
        odds=odds,
        opens_at=now - dt.timedelta(minutes=5),
        closes_at=now + dt.timedelta(hours=1),
    )
    transition(market, S.OPEN, actor=staff)
    return market


def outcome(market, code_or_team):
    if isinstance(code_or_team, Team):
        return market.outcomes.get(team=code_or_team)
    return market.outcomes.get(code=code_or_team)


def bet(user, market, picked, stake=100):
    return place_bet(
        user,
        market_id=market.pk,
        outcome_id=picked.pk,
        stake=stake,
        client_key=uuid.uuid4(),
    )[0]


def ready(league, market, staff):
    """Close the market, link the fixture and publish the match."""
    transition(market, S.CLOSED, actor=staff)
    league["fixture"].match = league["match"]
    league["fixture"].save()
    Match.objects.filter(pk=league["match"].pk).update(status=Match.Status.PUBLISHED)
    market.refresh_from_db()


def coins(user) -> int:
    return wallet_for(user).balance


# -- settling ------------------------------------------------------------------------------------


def test_winning_bet_paid_losing_bet_not(league, staff, fans):
    t = league["teams"]
    market = make_market(league, staff)
    win = bet(fans[0], market, outcome(market, t["Alpha"]), stake=100)
    lose = bet(fans[1], market, outcome(market, t["Bravo"]), stake=100)
    ready(league, market, staff)
    suggestion = suggest(market)
    assert suggestion["winners"] == [outcome(market, t["Alpha"]).pk]

    done, created = settle(market, actor=staff, winners=suggestion["winners"], reference="Match 1")
    assert created and done.version == 1 and done.evidence["match"] == league["match"].pk
    win.refresh_from_db()
    lose.refresh_from_db()
    assert (win.status, win.payout) == (B.WON, 250)
    assert (lose.status, lose.payout) == (B.LOST, 0)
    assert coins(fans[0]) == 1150  # 1000 - 100 + 250: the stake is not taken twice
    assert coins(fans[1]) == 900
    assert LedgerEntry.objects.filter(bet=lose, kind="PAYOUT").count() == 0
    market.refresh_from_db()
    assert market.status == S.SETTLED
    assert check_wallets() == []


def test_repeated_settlement_pays_once(league, staff, fans):
    market = make_market(league, staff)
    win = bet(fans[0], market, outcome(market, league["teams"]["Alpha"]))
    ready(league, market, staff)
    winners = suggest(market)["winners"]
    first, _ = settle(market, actor=staff, winners=winners)
    again, created = settle(market, actor=staff, winners=winners)
    assert not created and again.pk == first.pk
    assert LedgerEntry.objects.filter(bet=win, kind="PAYOUT").count() == 1
    assert coins(fans[0]) == 1150
    with pytest.raises(MarketError, match="correction"):
        settle(market, actor=staff, winners=[outcome(market, league["teams"]["Bravo"]).pk])


@pytest.mark.django_db(transaction=True)
def test_simultaneous_settlement_requests_pay_once(league, staff, fans):
    market = make_market(league, staff)
    for f in fans:
        bet(f, market, outcome(market, league["teams"]["Alpha"]))
    ready(league, market, staff)
    winners = suggest(market)["winners"]

    barrier = threading.Barrier(5)
    results = [None] * 5

    def run(i):
        try:
            barrier.wait()
            results[i] = settle(Market.objects.get(pk=market.pk), actor=staff, winners=winners)
        except Exception as exc:  # noqa: BLE001
            results[i] = exc
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(i,)) for i in range(5)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert all(isinstance(r, tuple) for r in results), results
    assert sum(1 for r in results if r[1]) == 1
    assert Settlement.objects.filter(market=market).count() == 1
    assert LedgerEntry.objects.filter(kind="PAYOUT").count() == 3
    assert [coins(f) for f in fans] == [1150, 1150, 1150]
    assert check_wallets() == []


def test_cannot_settle_before_close_or_without_published_match(league, staff, fans):
    market = make_market(league, staff)
    winners = [outcome(market, league["teams"]["Alpha"]).pk]
    with pytest.raises(MarketError):
        settle(market, actor=staff, winners=winners)  # still open, fixture not linked
    transition(market, S.CLOSED, actor=staff)
    with pytest.raises(MarketError, match="Link the fixture"):
        settle(market, actor=staff, winners=winners)
    league["fixture"].match = league["match"]
    league["fixture"].save()
    with pytest.raises(MarketError, match="isn't published"):
        settle(market, actor=staff, winners=winners)
    assert not Settlement.objects.exists()


def test_settling_against_the_result_needs_a_reason(league, staff, fans):
    market = make_market(league, staff)
    bravo = outcome(market, league["teams"]["Bravo"])
    bet(fans[0], market, bravo)
    ready(league, market, staff)
    with pytest.raises(MarketError) as exc:
        settle(market, actor=staff, winners=[bravo.pk])
    assert exc.value.code == "override"
    done, _ = settle(
        market, actor=staff, winners=[bravo.pk], override_reason="Alpha disqualified by referee"
    )
    assert done.reason == "Alpha disqualified by referee"
    assert coins(fans[0]) == 1200


def test_invalid_outcomes_are_refused(league, staff):
    market = make_market(league, staff)
    other = make_market(league, staff)
    ready(league, market, staff)
    for winners in ([other.outcomes.first().pk], [999999]):
        with pytest.raises(MarketError):
            settle(market, actor=staff, winners=winners, override_reason="x")
    with pytest.raises(MarketError):
        settle(market, actor=staff, winners=[], override_reason="x")
    assert not Settlement.objects.exists()


def test_team_that_did_not_play_is_refunded(league, staff, fans):
    t = league["teams"]
    market = make_market(league, staff, teams=("Alpha", "Bravo", "Delta"))
    on_delta = bet(fans[0], market, outcome(market, t["Delta"]), stake=200)
    on_bravo = bet(fans[1], market, outcome(market, t["Bravo"]), stake=100)
    ready(league, market, staff)
    s = suggest(market)
    assert s["voids"] == [outcome(market, t["Delta"]).pk]
    settle(market, actor=staff, winners=s["winners"], voids=s["voids"])
    on_delta.refresh_from_db()
    on_bravo.refresh_from_db()
    assert (on_delta.status, on_delta.payout, coins(fans[0])) == (B.VOID, 200, 1000)
    assert on_bravo.status == B.LOST


def test_bets_placed_after_the_real_start_are_refunded(league, staff, fans):
    market = make_market(league, staff)
    alpha = outcome(market, league["teams"]["Alpha"])
    early = bet(fans[0], market, alpha)
    Match.objects.filter(pk=league["match"].pk).update(started_at=timezone.now())
    late = bet(fans[1], market, alpha)
    ready(league, market, staff)
    settle(market, actor=staff, winners=[alpha.pk])
    early.refresh_from_db()
    late.refresh_from_db()
    assert early.status == B.WON and late.status == B.VOID
    assert coins(fans[1]) == 1000


@pytest.mark.parametrize(
    "category, teams, picked, expected",
    [
        (C.TOP_N, ("Bravo",), "yes", B.WON),  # Bravo 2nd, top 3
        (C.TOP_N, ("Charlie",), "no", B.LOST),  # Charlie 3rd: yes wins
        (C.H2H_PLACEMENT, ("Charlie", "Bravo"), "Bravo", B.WON),
        (C.H2H_KILLS, ("Alpha", "Bravo"), "Bravo", B.WON),  # 8 kills v 5
        (C.H2H_KILLS, ("Alpha", "Charlie"), "Alpha", B.VOID),  # 5 v 5: tie refunds
        (C.H2H_POINTS, ("Alpha", "Bravo"), "Alpha", B.VOID),  # 17 v 17: tie refunds
        (C.H2H_PLACEMENT, ("Alpha", "Delta"), "Alpha", B.VOID),  # Delta absent
        (C.TOP_N, ("Delta",), "yes", B.VOID),  # absent team
    ],
)
def test_market_rules(league, staff, fans, category, teams, picked, expected):
    market = make_market(league, staff, category=category, teams=teams)
    choice = outcome(market, league["teams"].get(picked) or picked)
    placed = bet(fans[0], market, choice)
    ready(league, market, staff)
    s = suggest(market)
    if s["kind"] == "VOID":
        void(market, actor=staff, reason=s["note"])
    else:
        settle(market, actor=staff, winners=s["winners"], voids=s["voids"])
    placed.refresh_from_db()
    assert placed.status == expected
    assert check_wallets() == []


# -- voiding -------------------------------------------------------------------------------------


def test_void_refunds_each_stake_once(league, staff, fans):
    market = make_market(league, staff)
    bets = [bet(f, market, outcome(market, league["teams"]["Alpha"]), stake=150) for f in fans]
    transition(market, S.SUSPENDED, actor=staff, reason="Lobby crashed")
    done, created = void(market, actor=staff, reason="Lobby crashed")
    again, created_again = void(market, actor=staff, reason="Lobby crashed")
    assert created and not created_again and again.pk == done.pk
    for b, f in zip(bets, fans, strict=True):
        b.refresh_from_db()
        assert (b.status, b.payout) == (B.VOID, 150)
        assert coins(f) == 1000
    assert LedgerEntry.objects.filter(kind="REFUND").count() == 3
    with pytest.raises(MarketError):
        void(market, actor=staff, reason="")
    with pytest.raises(MarketError):
        settle(market, actor=staff, winners=[outcome(market, league["teams"]["Alpha"]).pk])


def test_void_needs_a_reason(league, staff):
    market = make_market(league, staff)
    with pytest.raises(MarketError, match="reason"):
        void(market, actor=staff, reason="  ")


# -- corrections ---------------------------------------------------------------------------------


def test_correction_keeps_history_and_moves_the_difference(league, staff, fans):
    t = league["teams"]
    market = make_market(league, staff)
    alpha, bravo = outcome(market, t["Alpha"]), outcome(market, t["Bravo"])
    on_alpha = bet(fans[0], market, alpha, stake=100)  # 2.50
    on_bravo = bet(fans[1], market, bravo, stake=100)  # 3.00
    ready(league, market, staff)
    v1, _ = settle(market, actor=staff, winners=[alpha.pk])
    assert (coins(fans[0]), coins(fans[1])) == (1150, 900)

    key = uuid.uuid4()
    v2, created = correct(
        market,
        actor=staff,
        kind="SETTLE",
        winners=[bravo.pk],
        reason="Wrong team linked",
        key=str(key),
    )
    assert created and v2.version == 2 and v2.supersedes == v1
    again, created_again = correct(
        market,
        actor=staff,
        kind="SETTLE",
        winners=[bravo.pk],
        reason="Wrong team linked",
        key=str(key),
    )
    assert not created_again and again.pk == v2.pk
    assert (coins(fans[0]), coins(fans[1])) == (900, 1200)
    on_alpha.refresh_from_db()
    on_bravo.refresh_from_db()
    assert (on_alpha.status, on_alpha.payout) == (B.LOST, 0)
    assert (on_bravo.status, on_bravo.payout) == (B.WON, 300)
    # Nothing was overwritten: version 1 and its payout entry are still there.
    v1.refresh_from_db()
    assert list(v1.winning_outcomes.all()) == [alpha]
    assert LedgerEntry.objects.filter(bet=on_alpha, kind="PAYOUT", amount=250).exists()
    assert LedgerEntry.objects.filter(bet=on_alpha, kind="CORRECTION", amount=-250).exists()
    assert [s.version for s in market.settlements.all()] == [2, 1]
    assert check_wallets() == []


def test_correction_to_void_and_back(league, staff, fans):
    market = make_market(league, staff)
    alpha = outcome(market, league["teams"]["Alpha"])
    placed = bet(fans[0], market, alpha, stake=100)
    ready(league, market, staff)
    settle(market, actor=staff, winners=[alpha.pk])
    correct(market, actor=staff, kind="VOID", reason="Match replayed", key=str(uuid.uuid4()))
    placed.refresh_from_db()
    assert (placed.status, coins(fans[0])) == (B.VOID, 1000)
    market.refresh_from_db()
    assert market.status == S.VOID
    correct(
        market, actor=staff, kind="SETTLE", winners=[alpha.pk], reason="Replay cancelled",
        key=str(uuid.uuid4()),
    )  # fmt: skip
    assert coins(fans[0]) == 1150
    assert check_wallets() == []


def test_correction_stops_at_zero_and_records_shortfall(league, staff, fans):
    t = league["teams"]
    market = make_market(league, staff)
    alpha, bravo = outcome(market, t["Alpha"]), outcome(market, t["Bravo"])
    placed = bet(fans[0], market, alpha, stake=400)  # wins 1000
    ready(league, market, staff)
    settle(market, actor=staff, winners=[alpha.pk])
    assert coins(fans[0]) == 1600
    # The fan spends most of it on another market.
    other = make_market(league, staff)
    for _ in range(3):
        bet(fans[0], other, outcome(other, t["Charlie"]), stake=500)
    assert coins(fans[0]) == 100
    correct(
        market, actor=staff, kind="SETTLE", winners=[bravo.pk], reason="Fix", key=str(uuid.uuid4())
    )
    placed.refresh_from_db()
    assert coins(fans[0]) == 0
    assert (placed.status, placed.payout, placed.unrecovered) == (B.LOST, 0, 900)
    # Correcting back again doesn't hand over the 900 that was never taken back.
    correct(
        market, actor=staff, kind="SETTLE", winners=[alpha.pk], reason="Undo", key=str(uuid.uuid4())
    )
    placed.refresh_from_db()
    assert (placed.payout, placed.unrecovered, coins(fans[0])) == (1000, 0, 100)
    assert check_wallets() == []


def test_only_settled_markets_can_be_corrected(league, staff):
    market = make_market(league, staff)
    with pytest.raises(MarketError):
        correct(market, actor=staff, kind="VOID", reason="x", key=str(uuid.uuid4()))
    with pytest.raises(MarketError, match="reason"):
        correct(market, actor=staff, kind="VOID", reason="", key=str(uuid.uuid4()))


# -- through the API -----------------------------------------------------------------------------


def test_players_cannot_settle_void_or_correct(league, staff, fans):
    market = make_market(league, staff)
    ready(league, market, staff)
    client = as_user(fans[0])
    base = f"/api/v1/admin/predictions/markets/{market.pk}"
    winners = [outcome(market, league["teams"]["Alpha"]).pk]
    assert client.get(f"{base}/suggested-result").status_code == 403
    assert client.post(f"{base}/settle", {"winners": winners}, format="json").status_code == 403
    assert client.post(f"{base}/void", {"reason": "x"}, format="json").status_code == 403
    body = {"kind": "VOID", "reason": "x", "key": str(uuid.uuid4())}
    assert client.post(f"{base}/correct", body, format="json").status_code == 403
    assert not Settlement.objects.exists()


def test_full_life_of_a_bet_through_the_api(league, staff, fans):
    staff_client, fan_client = as_user(staff), as_user(fans[0])
    t = league["teams"]
    now = timezone.now()
    # 1. Staff create and open a market.
    resp = staff_client.post(
        "/api/v1/admin/predictions/markets",
        {
            "title": "Booyah, Day 1 Match 1",
            "category": "BOOYAH",
            "season": league["season"].pk,
            "fixture": league["fixture"].pk,
            "params": {"teams": [t["Alpha"].pk, t["Bravo"].pk]},
            "odds": {f"team:{t['Alpha'].pk}": "2.50", f"team:{t['Bravo'].pk}": "1.60"},
            "opens_at": (now - dt.timedelta(minutes=1)).isoformat(),
            "closes_at": (now + dt.timedelta(hours=1)).isoformat(),
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    market_id = resp.json()["id"]
    base = f"/api/v1/admin/predictions/markets/{market_id}"
    assert staff_client.post(f"{base}/transition", {"to": "OPEN"}, format="json").status_code == 200

    # 2. A fan sees it and places a bet.
    listed = fan_client.get("/api/v1/predictions/markets").json()["results"]
    alpha = next(o for o in listed[0]["outcomes"] if o["label"] == "Alpha")
    placed = fan_client.post(
        "/api/v1/predictions/bets",
        {
            "market": market_id,
            "outcome": alpha["id"],
            "stake": 200,
            "client_key": str(uuid.uuid4()),
        },
        format="json",
    )
    assert placed.status_code == 201 and placed.json()["balance"] == 800

    # 3. Staff close it, link the uploaded match, and settle from the suggested result.
    assert (
        staff_client.post(f"{base}/transition", {"to": "CLOSED"}, format="json").status_code == 200
    )
    linked = staff_client.patch(
        f"/api/v1/admin/predictions/fixtures/{league['fixture'].pk}",
        {"match": league["match"].pk},
        format="json",
    )
    assert linked.status_code == 200
    not_ready = staff_client.get(f"{base}/suggested-result")
    assert not_ready.status_code == 400 and not_ready.json()["code"] == "not_ready"
    Match.objects.filter(pk=league["match"].pk).update(status=Match.Status.PUBLISHED)
    suggestion = staff_client.get(f"{base}/suggested-result").json()
    assert suggestion["winners"] == [alpha["id"]]
    settled = staff_client.post(
        f"{base}/settle",
        {"winners": suggestion["winners"], "reference": "Day 1 logs"},
        format="json",
    )
    assert settled.status_code == 201, settled.content
    assert settled.json()["summary"]["won"] == 1
    assert (
        staff_client.post(
            f"{base}/settle", {"winners": suggestion["winners"]}, format="json"
        ).status_code
        == 200
    )

    # 4. The fan's wallet and history show the win.
    assert fan_client.get("/api/v1/predictions/wallet").json()["balance"] == 1300
    mine = fan_client.get("/api/v1/predictions/bets?status=won").json()["results"]
    assert [(b["status"], b["payout"], b["market"]["status"]) for b in mine] == [
        ("WON", 500, "SETTLED")
    ]
    kinds = [
        e["kind"] for e in fan_client.get("/api/v1/predictions/wallet/entries").json()["results"]
    ]
    assert kinds == ["PAYOUT", "STAKE", "INITIAL"]
    history = staff_client.get(f"{base}/settlements").json()
    assert history[0]["version"] == 1 and history[0]["by"] == "staff@tdl.test"
    assert check_wallets() == []


def test_leaderboard_keeps_its_three_measures_apart(league, staff, fans, settings):
    t = league["teams"]
    market = make_market(league, staff)
    alpha, bravo = outcome(market, t["Alpha"]), outcome(market, t["Bravo"])
    for _ in range(10):
        bet(fans[0], market, alpha, stake=10)  # 10 wins at 2.50
    for _ in range(9):
        bet(fans[1], market, bravo, stake=10)  # 9 losses
    bet(fans[1], market, alpha, stake=500)  # 1 big win
    wallet_for(fans[2])  # never bets
    ready(league, market, staff)
    settle(market, actor=staff, winners=[alpha.pk])
    client = APIClient()  # public while the site is public

    balance = client.get("/api/v1/predictions/leaderboard?metric=balance").json()["rows"]
    assert [(r["name"], r["balance"]) for r in balance] == [
        ("fan1@", 1660),  # 1000 - 590 + 1250
        ("fan0@", 1150),  # 1000 - 100 + 250
        ("fan2@", 1000),
    ]
    accuracy = client.get("/api/v1/predictions/leaderboard?metric=accuracy").json()["rows"]
    assert [(r["name"], r["accuracy"]) for r in accuracy] == [("fan0@", 1.0), ("fan1@", 0.1)]
    wins = client.get("/api/v1/predictions/leaderboard?metric=wins").json()["rows"]
    assert [(r["name"], r["won"]) for r in wins] == [("fan0@", 10), ("fan1@", 1)]
    assert "email" not in str(balance)
    assert client.get("/api/v1/predictions/leaderboard?metric=luck").status_code == 400
