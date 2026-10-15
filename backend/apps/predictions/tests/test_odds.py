"""Suggested odds from past results."""

import datetime as dt
import random
from decimal import Decimal

import pytest

from apps.accounts.models import StaffProfile
from apps.league.models import Match, MatchDay, ScoringRule, Season, Stage, Team
from apps.predictions.markets import MarketError, create_market
from apps.predictions.models import Fixture, Market
from apps.predictions.odds import DEFAULT_MATCHES_LEFT, price, session_length, suggest_odds
from apps.results.models import TeamMatchResult
from apps.results.standings import rebuild_season

from .test_settlement import as_user, make_user

pytestmark = pytest.mark.django_db
C = Market.Category
MARGIN = 0.08


@pytest.fixture(autouse=True)
def _margin(settings):
    settings.PREDICTIONS_ODDS_MARGIN = MARGIN


@pytest.fixture
def staff():
    user = make_user("staff@tdl.test")
    StaffProfile.objects.create(user=user)
    return user


@pytest.fixture
def league():
    """Four days of five 12-team matches. T01 is the best team and T12 the worst: each
    finishes about where its strength puts it, give or take a few places."""
    rule = ScoringRule.objects.create(
        name="Odds rule", placement_points={"1": 12, "2": 9, "3": 8, "4": 7, "5": 6, "6": 5}
    )
    season = Season.objects.create(name="Odds", slug="odds", scoring_rule=rule)
    stage = Stage.objects.create(season=season, name="Scrims")
    teams = [Team.objects.create(name=f"T{n:02}") for n in range(1, 13)]
    newcomer = Team.objects.create(name="Newcomer")
    rng = random.Random(3)
    days = []
    for d in range(4):
        day = MatchDay.objects.create(
            stage=stage, number=d + 1, date=dt.date(2026, 10, 1 + d), title=f"Day {d + 1} 8PM"
        )
        days.append(day)
        for number in range(1, 6):
            match = Match.objects.create(
                match_day=day,
                number=number,
                status=Match.Status.PUBLISHED,
                started_at=dt.datetime(2026, 10, 1 + d, 18 + number, tzinfo=dt.UTC),
            )
            order = sorted(teams, key=lambda t: teams.index(t) + rng.gauss(0, 3))
            for place, team in enumerate(order, start=1):
                kills = max(0, round(rng.gauss(10 - teams.index(team) * 0.6, 2.5)))
                TeamMatchResult.objects.create(
                    match=match, team=team, in_game_name=team.name, placement=place,
                    kills=kills, placement_points=0, kill_points=0, total_points=0,
                )  # fmt: skip
    rebuild_season(season)
    return {"season": season, "teams": teams, "newcomer": newcomer, "days": days}


def ids(league, *numbers):
    return [league["teams"][n - 1].pk for n in numbers]


def suggest(league, category, fixture=None, **params):
    return suggest_odds(season=league["season"], category=category, params=params, fixture=fixture)


def session_fixture(league, day=None, match_number=None, date=dt.date(2026, 10, 20)):
    return Fixture.objects.create(
        season=league["season"],
        date=date,
        session="8PM",
        match_number=match_number,
        scheduled_at=dt.datetime(2026, 10, 20, 19, tzinfo=dt.UTC),
        match_day=day,
    )


def overround(result) -> float:
    return sum(1 / float(o) for o in result["odds"].values())


# -- pricing --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("chance", "odds"),
    [
        (0.5, "1.85"),  # 1 / (0.5 x 1.08) = 1.851...
        (0.3, "3.05"),  # 3.086 rounded down to a 0.05 step
        (0.12, "7.7"),  # 7.716 rounded down to a 0.1 step
        (0.06, "15.0"),  # 15.43 rounded down to a 0.5 step
        (0.02, "46"),  # 46.29 rounded down to a whole number
        (0.99, "1.01"),  # never below the minimum
        (0.0001, "500"),  # never above 500
        (0.0, "500"),
    ],
)
def test_price_rounds_down_to_a_tidy_step(chance, odds):
    assert price(chance, MARGIN) == Decimal(odds)


def test_every_suggested_price_expects_to_lose_coins(league):
    """At suggested odds no outcome returns more than it takes in on average, so the
    leaderboard can't inflate (the simulation found random odds doubled the coins)."""
    for category, params in (
        (C.BOOYAH, {"teams": ids(league, 1, 2, 6, 12)}),
        (C.TOP_N, {"team": ids(league, 4)[0], "n": 3}),
        (C.H2H_POINTS, {"teams": ids(league, 1, 12)}),
    ):
        result = suggest(league, category, **params)
        for code, chance in result["chances"].items():
            if result["odds"][code] != "1.01":  # the floor can't take a margin
                # Chances come back rounded to 4 places, so take off the most rounding can add.
                assert (chance - 0.00005) * float(result["odds"][code]) <= 1 / (1 + MARGIN)


# -- one match ------------------------------------------------------------------------------------


def test_booyah_favours_the_stronger_team(league):
    result = suggest(league, C.BOOYAH, teams=ids(league, 1, 6, 12))
    best, middle, worst = (Decimal(result["odds"][f"team:{t}"]) for t in ids(league, 1, 6, 12))
    assert best < middle < worst
    assert result["lobby"] == 12 and result["matches"] == 1
    assert sum(result["chances"].values()) < 1
    assert any("aren't listed" in n for n in result["notes"])
    assert [t["matches"] for t in result["teams"]] == [20, 20, 20]


def test_booyah_chances_for_the_whole_lobby_add_up_to_one(league):
    result = suggest(league, C.BOOYAH, teams=ids(league, *range(1, 13)))
    assert sum(result["chances"].values()) == pytest.approx(1, abs=0.001)
    assert overround(result) == pytest.approx(1 + MARGIN, abs=0.06)
    assert not any("aren't listed" in n for n in result["notes"])


def test_suggestions_are_repeatable(league):
    one = suggest(league, C.BOOYAH, teams=ids(league, 1, 2))
    assert suggest(league, C.BOOYAH, teams=ids(league, 1, 2)) == one


def test_yes_no_markets_add_up_and_keep_the_margin(league):
    result = suggest(league, C.TOP_N, team=ids(league, 3)[0], n=5)
    assert set(result["odds"]) == {"yes", "no"}
    assert result["chances"]["yes"] + result["chances"]["no"] == pytest.approx(1)
    assert result["chances"]["yes"] > 0.5  # third best usually makes the top 5
    assert 1 + MARGIN <= overround(result) < 1.15


def test_head_to_head_leaves_ties_out(league):
    strong, weak = ids(league, 1, 12)
    result = suggest(league, C.H2H_PLACEMENT, teams=[strong, weak])
    assert result["chances"][f"team:{strong}"] > 0.85
    assert sum(result["chances"].values()) == pytest.approx(1)
    kills = suggest(league, C.H2H_KILLS, teams=[weak, strong])
    assert Decimal(kills["odds"][f"team:{strong}"]) < Decimal(kills["odds"][f"team:{weak}"])
    assert sum(kills["chances"].values()) == pytest.approx(1)


def test_team_kills_line(league):
    fixture = session_fixture(league, match_number=1)
    team = ids(league, 1)[0]
    low = suggest(league, C.TEAM_KILLS, fixture, team=team, line=1)
    assert low["odds"]["yes"] == "1.01"
    assert any("minimum" in n for n in low["notes"])
    high = suggest(league, C.TEAM_KILLS, fixture, team=team, line=40)
    assert Decimal(high["odds"]["yes"]) >= 100


def test_a_new_team_leans_on_league_averages(league):
    new = league["newcomer"].pk
    result = suggest(league, C.H2H_PLACEMENT, teams=[new, ids(league, 12)[0]])
    assert result["teams"][0] == {"id": new, "name": "Newcomer", "matches": 0}
    assert result["notes"][0].startswith("Newcomer has fewer than 5 published matches")
    assert result["chances"][f"team:{new}"] > 0.5  # an average team beats the worst


def test_no_published_results_is_refused(league):
    Match.objects.update(status=Match.Status.DRAFT)
    with pytest.raises(MarketError, match="no published results"):
        suggest(league, C.BOOYAH, teams=ids(league, 1, 2))


def test_draft_matches_dont_count(league):
    Match.objects.filter(match_day=league["days"][0]).update(status=Match.Status.DRAFT)
    result = suggest(league, C.BOOYAH, teams=ids(league, 1, 2))
    assert [t["matches"] for t in result["teams"]] == [15, 15]


def test_the_market_rules_still_apply(league):
    with pytest.raises(MarketError, match="exactly 2"):
        suggest(league, C.H2H_KILLS, teams=ids(league, 1, 2, 3))
    with pytest.raises(MarketError, match="whole-session fixture"):
        suggest(league, C.SESSION_WINNER, teams=ids(league, 1, 2))


# -- sessions and the season ----------------------------------------------------------------------


def test_session_length_comes_from_the_linked_day_or_a_typical_day(league):
    assert session_length(league["season"], session_fixture(league)) == 5
    Match.objects.filter(match_day=league["days"][0], number__gt=3).delete()
    linked = session_fixture(league, day=league["days"][0], date=dt.date(2026, 10, 21))
    assert session_length(league["season"], linked) == 3


def test_session_winner_and_most_booyahs(league):
    fixture = session_fixture(league)
    winner = suggest(league, C.SESSION_WINNER, fixture, teams=ids(league, 1, 2, 11, 12))
    chances = [winner["chances"][f"team:{t}"] for t in ids(league, 1, 2, 11, 12)]
    assert chances[0] > chances[1] > chances[3] and chances[0] > 0.3
    assert winner["matches"] == 5
    booyahs = suggest(league, C.MOST_BOOYAHS, fixture, teams=ids(league, *range(1, 13)))
    # Ties share the win, so the shares still add up to one across the whole lobby.
    assert sum(booyahs["chances"].values()) == pytest.approx(1, abs=0.001)


def test_overall_markets_start_from_the_current_table(league):
    leader, last = ids(league, 1, 12)
    close = suggest_odds(
        season=league["season"],
        category=C.OVERALL_WINNER,
        params={"teams": [leader, last]},
        matches_left=1,
    )
    assert close["chances"][f"team:{leader}"] > 0.95
    assert close["chances"][f"team:{last}"] == 0
    assert close["odds"][f"team:{last}"] == "500.00"
    assert close["matches_left"] == 1
    default = suggest(league, C.OVERALL_TOP_N, team=ids(league, 7)[0], n=5)
    assert default["matches_left"] == DEFAULT_MATCHES_LEFT
    assert default["chances"]["yes"] + default["chances"]["no"] == pytest.approx(1)


# -- API ------------------------------------------------------------------------------------------

URL = "/api/v1/admin/predictions/markets/suggest-odds"


def test_api_suggests_odds_a_market_can_be_made_with(league, staff):
    body = {
        "category": C.BOOYAH,
        "season": league["season"].pk,
        "params": {"teams": ids(league, 1, 2)},
    }
    response = as_user(staff).post(URL, body, format="json")
    assert response.status_code == 200, response.json()
    odds = response.json()["odds"]
    market = create_market(
        actor=staff,
        category=C.BOOYAH,
        title="Who wins?",
        season=league["season"],
        params=body["params"],
        odds=odds,
        opens_at=dt.datetime(2026, 10, 20, 18, tzinfo=dt.UTC),
        closes_at=dt.datetime(2026, 10, 20, 19, tzinfo=dt.UTC),
    )
    assert {o.code: str(o.odds) for o in market.outcomes.all()} == odds


def test_api_refusals(league, staff):
    api = as_user(staff)
    season = league["season"].pk
    other = Season.objects.create(
        name="Other", slug="other", scoring_rule=league["season"].scoring_rule
    )
    elsewhere = Fixture.objects.create(
        season=other,
        date=dt.date(2026, 10, 20),
        session="8PM",
        scheduled_at=dt.datetime(2026, 10, 20, tzinfo=dt.UTC),
    )
    bad = [
        {"category": C.H2H_KILLS, "season": season, "params": {"teams": ids(league, 1)}},
        {
            "category": C.BOOYAH,
            "season": season,
            "fixture": elsewhere.pk,
            "params": {"teams": ids(league, 1, 2)},
        },
        {
            "category": C.OVERALL_WINNER,
            "season": season,
            "params": {"teams": ids(league, 1, 2)},
            "matches_left": 61,
        },
    ]
    for body in bad:
        assert api.post(URL, body, format="json").status_code == 400, body
    fan = as_user(make_user("fan@tdl.test"))
    assert fan.post(URL, bad[0], format="json").status_code == 403
