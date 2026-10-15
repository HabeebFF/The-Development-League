"""Phase C session, date-range and season markets: session kills, session head-to-head and
top fragger, a table over any dates, and the season's top fragger."""

import datetime as dt
import uuid

import pytest
from django.utils import timezone

from apps.accounts.models import StaffProfile
from apps.league.models import Match, MatchDay, Player, ScoringRule, Season, Stage, Team
from apps.predictions.markets import (
    MarketError,
    create_market,
    outcome_specs,
    place_bet,
    transition,
)
from apps.predictions.models import Bet, Fixture, Market
from apps.predictions.odds import suggest_odds
from apps.predictions.services import check_wallets
from apps.predictions.settlement import settle, suggest
from apps.results.models import PlayerMatchResult, TeamMatchResult
from apps.results.standings import rebuild_season

from .test_settlement import make_user

pytestmark = pytest.mark.django_db
S, B, C = Market.Status, Bet.Status, Market.Category

# (day, match): [(team, place, kills)]. Each team has one player, who scores all its kills.
# Points: 12/9/8/7 for 1st to 4th plus 1 a kill.
#   Day 1: Alpha 28 pts (7 kills), Bravo 30 (9), Charlie 17 (1), Delta 15 (1).
#   Day 2: Charlie 22 (10), Delta 11 (2), Alpha 8 (0), Bravo 7 (0).
#   Days 1-2: Charlie 39, Bravo 37, Alpha 36, Delta 26.  Day 3 (later): Ace scores 20.
PLAYED = {
    (1, 1): [("Alpha", 1, 5), ("Bravo", 2, 3), ("Charlie", 3, 1), ("Delta", 4, 0)],
    (1, 2): [("Bravo", 1, 6), ("Alpha", 2, 2), ("Charlie", 3, 0), ("Delta", 4, 1)],
    (2, 1): [("Charlie", 1, 10), ("Delta", 2, 2), ("Alpha", 3, 0), ("Bravo", 4, 0)],
    (3, 1): [("Alpha", 1, 20), ("Bravo", 2, 0), ("Charlie", 3, 0), ("Delta", 4, 0)],
}
PLAYER = {"Alpha": "Ace", "Bravo": "Bo", "Charlie": "Cy", "Delta": "Dee", "Echo": "Echo"}


@pytest.fixture(autouse=True)
def _on(settings):
    settings.PREDICTIONS_ENABLED = True


@pytest.fixture
def staff():
    user = make_user("staff@tdl.test")
    StaffProfile.objects.create(user=user)
    return user


@pytest.fixture
def fans():
    return [make_user(f"fan{i}@tdl.test") for i in range(3)]


@pytest.fixture
def game():
    """Days 1 and 2 are ten and eight days ago; day 3 is yesterday. Nothing published yet."""
    rule = ScoringRule.objects.create(
        name="D rule", placement_points={"1": 12, "2": 9, "3": 8, "4": 7}
    )
    season = Season.objects.create(name="S4", slug="s4", scoring_rule=rule)
    stage = Stage.objects.create(season=season, name="Scrims")
    today = timezone.localdate()
    dates = {1: today - dt.timedelta(days=10), 2: today - dt.timedelta(days=8)}
    dates[3] = today - dt.timedelta(days=1)
    days = {
        n: MatchDay.objects.create(stage=stage, number=n, date=d, title=f"Day {n}")
        for n, d in dates.items()
    }
    teams = {n: Team.objects.create(name=n) for n in PLAYER}
    players = {
        name: Player.objects.create(
            game_uid=9100 + i,
            current_name_raw=name,
            display_name=name,
            search_name=name.casefold(),
            current_team=teams[team],
        )  # fmt: skip
        for i, (team, name) in enumerate(PLAYER.items())
    }
    matches = {}
    for (d, n), rows in PLAYED.items():
        match = Match.objects.create(match_day=days[d], number=n, status=Match.Status.PROCESSING)
        matches[d, n] = match
        for team, place, kills in rows:
            TeamMatchResult.objects.create(
                match=match, team=teams[team], in_game_name=team, placement=place,
                kills=kills, placement_points=0, kill_points=0, total_points=0,
            )  # fmt: skip
            name = PLAYER[team]
            PlayerMatchResult.objects.create(
                match=match, player=players[name], team=teams[team], raw_name=name,
                display_name=name, kills=kills,
            )  # fmt: skip
    later = timezone.now() + dt.timedelta(hours=1)
    session = Fixture.objects.create(
        season=season, date=dates[1], session="8PM", match_number=None, scheduled_at=later
    )
    return {
        "season": season,
        "days": days,
        "dates": dates,
        "matches": matches,
        "teams": teams,
        "players": players,
        "session": session,
    }


def resolve(game, params):
    """Names to ids, and day numbers to dates, as staff would send them."""
    t, p = game["teams"], game["players"]
    out = dict(params)
    for key, lookup in (("team", t), ("player", p)):
        if key in out:
            out[key] = lookup[out[key]].pk
    for key, lookup in (("teams", t), ("players", p)):
        if key in out:
            out[key] = [lookup[n].pk for n in out[key]]
    for key in ("from", "to"):
        if isinstance(out.get(key), int):
            out[key] = game["dates"][out[key]].isoformat()
    return out


def market(game, by, category, odds=None, **params):
    params = resolve(game, params)
    try:
        codes = [s["code"] for s in outcome_specs(category, params)]
    except (KeyError, ValueError):
        codes = []  # bad params: create_market says why
    now = timezone.now()
    session = category in (C.SESSION_KILLS, C.SESSION_H2H, C.SESSION_FRAGGER)
    m = create_market(
        actor=by,
        category=category,
        title=f"{category} market",
        season=game["season"],
        fixture=game["session"] if session else None,
        params=params,
        odds=odds or {c: "2.00" for c in codes},
        opens_at=now - dt.timedelta(minutes=5),
        closes_at=now + dt.timedelta(hours=1),
    )
    transition(m, S.OPEN, actor=by)
    return m


def publish(game, days=(1, 2, 3)):
    Match.objects.filter(match_day__number__in=days).update(status=Match.Status.PUBLISHED)
    game["session"].match_day = game["days"][1]
    game["session"].save()
    rebuild_season(game["season"])


def result(m, game, days=(1, 2, 3)) -> tuple[list[str], list[str], dict]:
    """The suggested result as (winner labels, refunded labels, raw)."""
    publish(game, days)
    transition(m, S.CLOSED, actor=m.created_by)
    s = suggest(Market.objects.get(pk=m.pk))
    labels = dict(m.outcomes.values_list("pk", "label"))
    return [labels[w] for w in s["winners"]], [labels[v] for v in s["voids"]], s


def outcome(m, name, game):
    if name in game["teams"]:
        return m.outcomes.get(team=game["teams"][name])
    if name in game["players"]:
        return m.outcomes.get(player=game["players"][name])
    return m.outcomes.get(code=name)


def bet(user, m, choice, stake=100):
    return place_bet(
        user, market_id=m.pk, outcome_id=choice.pk, stake=stake, client_key=uuid.uuid4()
    )[0]


# -- creating ------------------------------------------------------------------------------------


def test_labels(game, staff):
    kills = market(game, staff, C.SESSION_KILLS, team="Alpha", line=7)
    assert list(kills.outcomes.values_list("label", flat=True)) == [
        "Alpha: over 6.5 kills",
        "Alpha: under 6.5 kills",
    ]
    top = market(game, staff, C.RANGE_TOP_N, team="Alpha", n=3, **{"from": 1, "to": 2})
    assert list(top.outcomes.values_list("code", flat=True)) == ["yes", "no"]
    frag = market(game, staff, C.SEASON_FRAGGER, players=["Ace", "Cy"])
    assert list(frag.outcomes.values_list("label", flat=True)) == ["Ace", "Cy"]


@pytest.mark.parametrize(
    ("category", "params", "message"),
    [
        (C.SESSION_KILLS, {"team": "Alpha", "line": 201}, "1 to 200"),
        (C.SESSION_H2H, {"teams": ["Alpha"]}, "2"),
        (C.SESSION_FRAGGER, {"players": ["Ace"]}, "2"),
        (C.RANGE_WINNER, {"teams": ["Alpha", "Bravo"]}, "from and to"),
        (C.RANGE_WINNER, {"teams": ["Alpha", "Bravo"], "from": 2, "to": 1}, "before the start"),
        (
            C.RANGE_FRAGGER,
            {"players": ["Ace", "Bo"], "from": "2026-01-01", "to": "2026-03-31"},
            "at most 62 days",
        ),
        (C.RANGE_TOP_N, {"team": "Alpha", "n": 4, "from": 1, "to": 2}, "3, 5 or 10"),
    ],
)
def test_bad_params_are_refused(game, staff, category, params, message):
    with pytest.raises(MarketError, match=message):
        market(game, staff, category, **params)


def test_session_markets_need_a_session_fixture(game, staff):
    now = timezone.now()
    params = resolve(game, {"team": "Alpha", "line": 7})
    with pytest.raises(MarketError):
        create_market(
            actor=staff, category=C.SESSION_KILLS, title="x", season=game["season"],
            fixture=None, params=params, odds={"yes": "2.00", "no": "2.00"},
            opens_at=now, closes_at=now + dt.timedelta(hours=1),
        )  # fmt: skip


# -- settling: sessions --------------------------------------------------------------------------


@pytest.mark.parametrize(("line", "code"), [(7, "yes"), (8, "no")])
def test_session_kills(game, staff, line, code):
    winners, _, _ = result(market(game, staff, C.SESSION_KILLS, team="Alpha", line=line), game)
    assert winners == [f"Alpha: {'over' if code == 'yes' else 'under'} {line - 0.5:g} kills"]


def test_session_kills_for_a_team_that_didnt_play_is_void(game, staff):
    m = market(game, staff, C.SESSION_KILLS, team="Echo", line=1)
    assert result(m, game)[2]["kind"] == "VOID"


def test_session_head_to_head_and_tie(game, staff):
    winners, _, _ = result(market(game, staff, C.SESSION_H2H, teams=["Alpha", "Bravo"]), game)
    assert winners == ["Bravo"]  # 30 v 28
    tie = market(game, staff, C.SESSION_H2H, teams=["Alpha", "Charlie"])
    TeamMatchResult.objects.filter(match=game["matches"][1, 1], team__name="Charlie").update(
        kills=12
    )  # Charlie 28 too
    rebuild_season(game["season"])
    transition(tie, S.CLOSED, actor=staff)
    assert suggest(Market.objects.get(pk=tie.pk))["kind"] == "VOID"


def test_session_top_fragger_adds_up_the_session(game, staff):
    winners, voids, s = result(
        market(game, staff, C.SESSION_FRAGGER, players=["Ace", "Bo", "Cy", "Echo"]), game
    )
    assert (winners, voids) == (["Bo"], ["Echo"])  # Bo 9, Ace 7; day 2 doesn't count
    assert s["dead_heat"] == 1


# -- settling: date ranges -----------------------------------------------------------------------


def test_range_winner_uses_only_the_matches_in_the_dates(game, staff):
    m = market(
        game, staff, C.RANGE_WINNER, teams=["Alpha", "Bravo", "Charlie"], **{"from": 1, "to": 2}
    )
    winners, _, s = result(m, game)
    assert winners == ["Charlie"]  # 39; day 3's Alpha Booyah is outside the dates
    table = {row["name"]: row["points"] for row in s["evidence"]["standings"]}
    assert table == {"Charlie": 39, "Bravo": 37, "Alpha": 36}


@pytest.mark.parametrize(("team", "n", "code"), [("Alpha", 3, "yes"), ("Delta", 3, "no")])
def test_range_top_n(game, staff, team, n, code):
    m = market(game, staff, C.RANGE_TOP_N, team=team, n=n, **{"from": 1, "to": 2})
    winners, _, s = result(m, game)
    assert [o.code for o in m.outcomes.filter(label__in=winners)] == [code]


def test_range_top_n_for_a_team_that_didnt_play_is_void(game, staff):
    m = market(game, staff, C.RANGE_TOP_N, team="Echo", n=3, **{"from": 1, "to": 2})
    assert result(m, game)[2]["kind"] == "VOID"


def test_range_fragger_dead_heat_pays_half(game, staff, fans):
    PlayerMatchResult.objects.filter(display_name="Bo", match=game["matches"][2, 1]).update(
        kills=2
    )  # Bo 11, level with Cy
    m = market(game, staff, C.RANGE_FRAGGER, players=["Bo", "Cy", "Ace"], **{"from": 1, "to": 2})
    bo = bet(fans[0], m, outcome(m, "Bo", game), stake=100)
    ace = bet(fans[1], m, outcome(m, "Ace", game), stake=100)
    winners, _, s = result(m, game)
    assert sorted(winners) == ["Bo", "Cy"] and s["dead_heat"] == 2
    settle(Market.objects.get(pk=m.pk), actor=staff, winners=s["winners"])
    bo.refresh_from_db()
    ace.refresh_from_db()
    assert (bo.status, bo.payout) == (B.WON, 100)  # 100 x 2.00 / 2
    assert (ace.status, ace.payout) == (B.LOST, 0)
    assert check_wallets() == []


def test_range_isnt_ready_until_the_last_date_is_over(game, staff):
    today = timezone.localdate().isoformat()
    m = market(game, staff, C.RANGE_WINNER, teams=["Alpha", "Bravo"], **{"from": 1, "to": today})
    publish(game)
    transition(m, S.CLOSED, actor=staff)
    with pytest.raises(MarketError, match="settle it after that"):
        suggest(Market.objects.get(pk=m.pk))


def test_range_waits_for_unpublished_matches(game, staff):
    m = market(game, staff, C.RANGE_WINNER, teams=["Alpha", "Bravo"], **{"from": 1, "to": 2})
    publish(game, days=(1, 3))
    Match.objects.filter(match_day=game["days"][2]).update(status=Match.Status.NEEDS_REVIEW)
    transition(m, S.CLOSED, actor=staff)
    with pytest.raises(MarketError, match="still need publishing"):
        suggest(Market.objects.get(pk=m.pk))


# -- settling: the season ------------------------------------------------------------------------


def test_season_top_fragger(game, staff):
    winners, voids, _ = result(
        market(game, staff, C.SEASON_FRAGGER, players=["Ace", "Cy", "Echo"]), game
    )
    assert (winners, voids) == (["Ace"], ["Echo"])  # 27 v 11


def test_season_top_fragger_not_listed_loses_everyone(game, staff):
    winners, _, s = result(market(game, staff, C.SEASON_FRAGGER, players=["Bo", "Dee"]), game)
    assert winners == [] and s["kind"] != "VOID"  # Ace has the most kills


# -- odds ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("category", "params"),
    [
        (C.SESSION_KILLS, {"team": "Bravo", "line": 8}),
        (C.SESSION_H2H, {"teams": ["Alpha", "Bravo"]}),
        (C.SESSION_FRAGGER, {"players": ["Ace", "Cy"]}),
        (C.RANGE_WINNER, {"teams": ["Alpha", "Charlie"], "from": 1, "to": 2}),
        (C.RANGE_TOP_N, {"team": "Charlie", "n": 3, "from": 1, "to": 2}),
        (C.RANGE_FRAGGER, {"players": ["Ace", "Cy"], "from": 1, "to": 2}),
        (C.SEASON_FRAGGER, {"players": ["Ace", "Dee"]}),
    ],
)
def test_suggested_odds_cover_every_new_market(game, staff, category, params):
    publish(game)
    params = resolve(game, params)
    session = category in (C.SESSION_KILLS, C.SESSION_H2H, C.SESSION_FRAGGER)
    got = suggest_odds(
        season=game["season"], category=category, params=params,
        fixture=game["session"] if session else None, matches_left=3,
    )  # fmt: skip
    assert set(got["odds"]) == {s["code"] for s in outcome_specs(category, params)}
    assert all(1 <= float(o) <= 500 for o in got["odds"].values())


def test_season_fragger_odds_count_kills_already_scored(game, staff):
    publish(game)
    p = game["players"]
    got = suggest_odds(
        season=game["season"], category=C.SEASON_FRAGGER,
        params={"players": [p["Ace"].pk, p["Dee"].pk]}, matches_left=1,
    )  # fmt: skip
    # Ace leads 27 to 3 with one match left: almost certain.
    assert got["chances"][f"player:{p['Ace'].pk}"] > 0.95


def test_session_kills_odds_follow_history(game, staff):
    publish(game)
    t = game["teams"]
    low = suggest_odds(
        season=game["season"], category=C.SESSION_KILLS,
        params={"team": t["Charlie"].pk, "line": 1}, fixture=game["session"],
    )  # fmt: skip
    high = suggest_odds(
        season=game["season"], category=C.SESSION_KILLS,
        params={"team": t["Charlie"].pk, "line": 150}, fixture=game["session"],
    )  # fmt: skip
    assert low["chances"]["yes"] > 0.5 > 0.05 > high["chances"]["yes"]
