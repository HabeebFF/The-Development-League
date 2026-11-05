"""Bet builder: picks on the same match in one multiple, with clashes refused and odds cut."""

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.league.models import Player, RosterEntry
from apps.predictions.builder import MAX_PER_MATCH
from apps.predictions.markets import MarketError, create_market, transition
from apps.predictions.models import Market

from . import test_multiples as tm
from .test_multiples import balance, decide, fresh, market, pick, place
from .test_settlement import as_user

pytestmark = pytest.mark.django_db
S, C = Market.Status, Market.Category
# The multiples tests' fixtures, used here too.
_on, fan, lg, staff = tm._on, tm.fan, tm.lg, tm.staff


def make(lg, staff, category, params, odds, where="m1"):
    now = timezone.now()
    m = create_market(
        actor=staff, category=category, title=f"{category} {params}", season=lg["season"],
        fixture=lg[where], params=params, odds=odds,
        opens_at=now - dt.timedelta(minutes=5), closes_at=now + dt.timedelta(hours=1),
    )  # fmt: skip
    return transition(m, S.OPEN, actor=staff)


def top3(lg, staff, team="Alpha", yes="2.00", no="1.80"):
    t = lg["teams"][team]
    return make(lg, staff, C.TOP_N, {"team": t.pk, "n": 3}, {"yes": yes, "no": no})


def kills(lg, staff, team="Alpha"):
    t = lg["teams"][team]
    return make(lg, staff, C.TEAM_KILLS, {"team": t.pk, "line": 8}, {"yes": "2.00", "no": "1.80"})


def code(m, c):
    return {"market": m.pk, "outcome": m.outcomes.get(code=c).pk}


def legs(multiple):
    return [(leg.odds_accepted, leg.odds_counted) for leg in fresh(multiple).legs.order_by("pk")]


def test_two_booyahs_in_one_match_are_refused(lg, staff, fan):
    a = market(lg, staff, "m1")
    b = make(lg, staff, C.FINISH_BAND, {"team": lg["teams"]["Bravo"].pk}, dict.fromkeys(
        ("band:1", "band:2", "band:4", "band:7"), "3.00"))  # fmt: skip
    with pytest.raises(MarketError) as err:
        place(fan, [pick(a, "Alpha"), code(b, "band:1")])
    assert err.value.code == "contradiction"
    assert balance(fan) == 1000


def test_booyah_and_outside_top_3_are_refused(lg, staff, fan):
    a, b = market(lg, staff, "m1"), top3(lg, staff)
    with pytest.raises(MarketError, match="can't both happen"):
        place(fan, [pick(a, "Alpha"), code(b, "no")])


def test_a_pick_made_certain_by_another_counts_as_1(lg, staff, fan):
    a, b = market(lg, staff, "m1"), top3(lg, staff)
    m = place(fan, [pick(a, "Alpha"), code(b, "yes")])
    assert legs(m) == [(Decimal("2.00"), Decimal("2.00")), (Decimal("2.00"), Decimal("1.00"))]
    assert m.odds == Decimal("2.00") and m.potential_return == 200


def test_same_team_is_cut_25_and_other_teams_10(lg, staff, fan):
    a, b = market(lg, staff, "m1"), kills(lg, staff, "Alpha")
    m = place(fan, [pick(a, "Alpha"), code(b, "yes")])
    assert legs(m)[1] == (Decimal("2.00"), Decimal("1.50"))  # 2.00 x 0.75
    assert m.odds == Decimal("3.00")
    c = kills(lg, staff, "Bravo")
    m2 = place(fan, [pick(a, "Alpha"), code(c, "yes")])
    assert legs(m2)[1] == (Decimal("2.00"), Decimal("1.80"))  # 2.00 x 0.90


def test_a_player_counts_as_their_team(lg, staff, fan):
    alpha = lg["teams"]["Alpha"]
    star = Player.objects.create(
        game_uid=1, current_name_raw="Star", display_name="Star", search_name="star"
    )
    RosterEntry.objects.create(player=star, team=alpha, season=lg["season"])
    a = market(lg, staff, "m1")
    p = make(
        lg, staff, C.PLAYER_KILLS, {"player": star.pk, "line": 4}, {"yes": "2.40", "no": "1.50"}
    )
    m = place(fan, [pick(a, "Alpha"), code(p, "yes")])
    assert legs(m)[1] == (Decimal("2.40"), Decimal("1.80"))


def test_cut_odds_never_go_below_1(lg, staff, fan):
    a = market(lg, staff, "m1")
    b = make(lg, staff, C.TEAM_KILLS, {"team": lg["teams"]["Alpha"].pk, "line": 2},
             {"yes": "1.10", "no": "6.00"})  # fmt: skip
    assert legs(place(fan, [pick(a, "Alpha"), code(b, "yes")]))[1][1] == Decimal("1.00")


def test_at_most_4_picks_from_one_match(lg, staff, fan):
    picks = [code(kills(lg, staff, t), "yes") for t in ("Alpha", "Bravo", "Charlie", "Delta")]
    picks.append(code(top3(lg, staff, "Delta"), "yes"))
    with pytest.raises(MarketError) as err:
        place(fan, picks)
    assert err.value.code == "same_match_limit" and MAX_PER_MATCH == 4


def test_picks_on_other_matches_keep_their_odds(lg, staff, fan):
    a, b, c = market(lg, staff, "m1"), kills(lg, staff, "Alpha"), market(lg, staff, "sat")
    m = place(fan, [pick(a, "Alpha"), code(b, "yes"), pick(c, "Bravo")])
    assert legs(m)[2] == (Decimal("3.00"), Decimal("3.00"))
    assert m.odds == Decimal("9.00")  # 2.00 x 1.50 x 3.00


def test_it_pays_at_the_cut_odds_and_a_loss_loses_it(lg, staff, fan):
    a, b = market(lg, staff, "m1"), kills(lg, staff, "Alpha")
    m = place(fan, [pick(a, "Alpha"), code(b, "yes")], stake=100)
    assert balance(fan) == 900
    decide(a, staff, winners=["Alpha"])
    bm = Market.objects.get(pk=b.pk)
    transition(bm, S.CLOSED, actor=staff)
    from apps.predictions import settlement as st

    st._decide(bm.pk, kind="SETTLE", actor=staff, winners=[bm.outcomes.get(code="yes").pk],
               voids=[], allowed_from={S.CLOSED}, dead_heat=1, reason="t")  # fmt: skip
    assert fresh(m).payout == 300 and balance(fan) == 1200
    lost = place(
        fan,
        [
            pick(market(lg, staff, "m2"), "Alpha"),
            pick(market(lg, staff, "m2", category=C.FIRST_OUT), "Bravo"),
        ],
    )  # noqa: E501
    assert fresh(lost).status == "PENDING"


def test_quote_shows_the_cut_before_placing(lg, staff, fan):
    a, b = market(lg, staff, "m1"), kills(lg, staff, "Alpha")
    body = {"picks": [pick(a, "Alpha", odds=False), code(b, "yes")]}
    r = as_user(fan).post("/api/v1/predictions/multiples/quote", body, format="json")
    assert r.status_code == 200, r.content
    data = r.json()
    assert data["builder"] is True and data["odds"] == "3.00"
    assert [p["counted"] for p in data["picks"]] == ["2.00", "1.50"]
    assert "same team" in data["picks"][1]["note"]
    bad = {"picks": [pick(a, "Alpha", odds=False), code(top3(lg, staff), "no")]}
    r = as_user(fan).post("/api/v1/predictions/multiples/quote", bad, format="json")
    assert r.status_code == 400 and r.json()["code"] == "contradiction"
    assert as_user(fan).get("/api/v1/predictions/wallet").json()["balance"] == 1000
    placed = (
        as_user(fan)
        .post(
            "/api/v1/predictions/multiples",
            {**body, "stake": 100, "client_key": str(uuid.uuid4())},
            format="json",
        )
        .json()
    )
    assert placed["odds"] == "3.00"
    assert [p["odds_counted"] for p in placed["picks"]] == ["2.00", "1.50"]
