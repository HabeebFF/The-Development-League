"""Phase C match markets: totals, handicaps, finishing bands, firsts and player markets."""

import datetime as dt
import uuid

import pytest
from django.utils import timezone

from apps.accounts.models import Membership, StaffProfile
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
from apps.results.models import MatchEvent, PlayerMatchResult, TeamMatchResult
from apps.results.standings import rebuild_season

from .test_settlement import as_user, make_user

pytestmark = pytest.mark.django_db
S, B, C = Market.Status, Bet.Status, Market.Category
K = MatchEvent.Kind


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
    """One match. Points: 12/9/8/7 for 1st to 4th plus 1 a kill.

    Alpha 1st (8 kills, 20 pts), Bravo 2nd (11, 20), Charlie 3rd (2, 10), Delta 4th (0, 7).
    Players: Ace (Alpha) 5 kills, 1300 damage; Ash (Alpha) 3; Bo (Bravo) 5; Bea (Bravo) 6;
    Cy (Charlie) 2; Dee (Delta) 0. Echo plays for Echo, a team that isn't in this match.
    First blood: Bravo at 40s (an Alpha player killed a team-mate at 20s, which doesn't
    count). First deaths: Dee at 90s.
    """
    rule = ScoringRule.objects.create(
        name="C rule", placement_points={"1": 12, "2": 9, "3": 8, "4": 7}
    )
    season = Season.objects.create(name="S3", slug="s3", scoring_rule=rule)
    stage = Stage.objects.create(season=season, name="Scrims")
    day = MatchDay.objects.create(stage=stage, number=1, date=dt.date(2026, 10, 18))
    teams = {n: Team.objects.create(name=n) for n in ("Alpha", "Bravo", "Charlie", "Delta", "Echo")}
    match = Match.objects.create(match_day=day, number=1, status=Match.Status.PROCESSING)
    for name, place, kills in (
        ("Alpha", 1, 8),
        ("Bravo", 2, 11),
        ("Charlie", 3, 2),
        ("Delta", 4, 0),
    ):
        TeamMatchResult.objects.create(
            match=match, team=teams[name], in_game_name=name, placement=place, kills=kills,
            placement_points=0, kill_points=0, total_points=0,
        )  # fmt: skip
    players = {}
    for n, (name, team, kills, damage) in enumerate(
        (
            ("Ace", "Alpha", 5, 1300),
            ("Ash", "Alpha", 3, 700),
            ("Bo", "Bravo", 5, 1200),
            ("Bea", "Bravo", 6, 1500),
            ("Cy", "Charlie", 2, 400),
            ("Dee", "Delta", 0, 90),
            ("Echo", "Echo", 0, None),
        )
    ):
        players[name] = Player.objects.create(
            game_uid=9000 + n, current_name_raw=name, display_name=name,
            search_name=name.casefold(), current_team=teams[team],
        )  # fmt: skip
        if team != "Echo":
            PlayerMatchResult.objects.create(
                match=match, player=players[name], team=teams[team], raw_name=name,
                display_name=name, kills=kills, damage_dealt=damage,
            )  # fmt: skip
    ev = {"match": match, "source": MatchEvent.Source.REPLAY_INFO}
    MatchEvent.objects.create(
        **ev, kind=K.KILL, game_time_s=20, actor_team=teams["Alpha"], target_team=teams["Alpha"]
    )
    MatchEvent.objects.create(
        **ev, kind=K.KILL, game_time_s=40, actor_team=teams["Bravo"], target_team=teams["Delta"]
    )
    MatchEvent.objects.create(
        **ev, kind=K.KILL, game_time_s=55, actor_team=teams["Alpha"], target_team=teams["Charlie"]
    )
    for at, name in ((90, "Dee"), (300, "Cy"), (600, "Ash")):
        MatchEvent.objects.create(
            **ev, kind=K.DEATH, game_time_s=at, actor_player=players[name],
            actor_team=players[name].current_team,
        )  # fmt: skip
    later = timezone.now() + dt.timedelta(hours=1)
    fixture = Fixture.objects.create(
        season=season, date=day.date, session="8PM", match_number=1, scheduled_at=later
    )
    return {
        "season": season,
        "match": match,
        "teams": teams,
        "players": players,
        "fixture": fixture,
    }


def market(game, by, category, odds=None, **params):
    t, p = game["teams"], game["players"]
    for key in ("team", "player"):
        if key in params:
            params[key] = (t if key == "team" else p)[params[key]].pk
    for key in ("teams", "players"):
        if key in params:
            params[key] = [(t if key == "teams" else p)[n].pk for n in params[key]]
    try:
        codes = [s["code"] for s in outcome_specs(category, params)]
    except (KeyError, ValueError):
        codes = []  # bad params: create_market says why
    now = timezone.now()
    m = create_market(
        actor=by,
        category=category,
        title=f"{category} market",
        season=game["season"],
        fixture=game["fixture"],
        params=params,
        odds=odds or {c: "2.00" for c in codes},
        opens_at=now - dt.timedelta(minutes=5),
        closes_at=now + dt.timedelta(hours=1),
    )
    transition(m, S.OPEN, actor=by)
    return m


def publish(game):
    Match.objects.filter(pk=game["match"].pk).update(status=Match.Status.PUBLISHED)
    game["fixture"].match = game["match"]
    game["fixture"].save()
    rebuild_season(game["season"])


def outcome(m, code_or_name, game):
    if code_or_name in game["teams"]:
        return m.outcomes.get(team=game["teams"][code_or_name])
    if code_or_name in game["players"]:
        return m.outcomes.get(player=game["players"][code_or_name])
    return m.outcomes.get(code=code_or_name)


def result(m, game) -> tuple[list[str], list[str], dict]:
    """The suggested result as (winner labels, refunded labels, raw)."""
    publish(game)
    transition(m, S.CLOSED, actor=m.created_by)
    s = suggest(Market.objects.get(pk=m.pk))
    labels = dict(m.outcomes.values_list("pk", "label"))
    return [labels[w] for w in s["winners"]], [labels[v] for v in s["voids"]], s


def bet(user, m, choice, stake=100):
    return place_bet(
        user, market_id=m.pk, outcome_id=choice.pk, stake=stake, client_key=uuid.uuid4()
    )[0]


# -- creating ------------------------------------------------------------------------------------


def test_labels_read_like_a_bookmaker(game, staff):
    labels = {
        C.TOTAL_KILLS: market(game, staff, C.TOTAL_KILLS, line=20),
        C.KILLS_HANDICAP: market(game, staff, C.KILLS_HANDICAP, teams=["Alpha", "Bravo"], line=3),
        C.FINISH_BAND: market(game, staff, C.FINISH_BAND, team="Charlie"),
        C.PLAYER_KILLS: market(game, staff, C.PLAYER_KILLS, player="Ace", line=4),
        C.PLAYER_DAMAGE: market(game, staff, C.PLAYER_DAMAGE, player="Ace", line=1000),
    }
    got = {k: [o.label for o in m.outcomes.order_by("sort")] for k, m in labels.items()}
    assert got == {
        C.TOTAL_KILLS: ["Over 19.5 kills", "Under 19.5 kills"],
        C.KILLS_HANDICAP: ["Alpha -2.5 kills", "Bravo +2.5 kills"],
        C.FINISH_BAND: [
            "Charlie: 1st",
            "Charlie: 2nd-3rd",
            "Charlie: 4th-6th",
            "Charlie: 7th or lower",
        ],
        C.PLAYER_KILLS: ["Ace: over 3.5 kills", "Ace: under 3.5 kills"],
        C.PLAYER_DAMAGE: ["Ace: over 999.5 damage", "Ace: under 999.5 damage"],
    }
    fragger = market(game, staff, C.TOP_FRAGGER, players=["Ace", "Bea"])
    assert [o.player.display_name for o in fragger.outcomes.order_by("sort")] == ["Ace", "Bea"]


@pytest.mark.parametrize(
    ("category", "params", "message"),
    [
        (C.TOTAL_KILLS, {"line": 0}, "kills line"),
        (C.KILLS_HANDICAP, {"teams": ["Alpha", "Bravo"], "line": 31}, "handicap"),
        (C.POINTS_HANDICAP, {"teams": ["Alpha"], "line": 5}, "exactly 2"),
        (C.PLAYER_DAMAGE, {"player": "Ace", "line": 50}, "damage line"),
        (C.PLAYER_H2H, {"players": ["Ace", "Bo", "Cy"]}, "exactly 2"),
        (C.TOP_FRAGGER, {"players": ["Ace"]}, "at least 2"),
        (C.FIRST_DEATH, {"players": ["Ace", "Ace"]}, "twice"),
    ],
)
def test_bad_params_are_refused(game, staff, category, params, message):
    with pytest.raises(MarketError, match=message):
        market(game, staff, category, **params)


def test_unknown_player_is_refused(game, staff):
    with pytest.raises(MarketError, match="Unknown player"):
        create_market(
            actor=staff, category=C.PLAYER_KILLS, title="x", season=game["season"],
            fixture=game["fixture"], params={"player": 999999, "line": 2},
            odds={"yes": "2.00", "no": "2.00"}, opens_at=timezone.now(),
            closes_at=timezone.now() + dt.timedelta(hours=1),
        )  # fmt: skip


def test_new_match_markets_need_a_one_match_fixture(game, staff):
    whole = Fixture.objects.create(
        season=game["season"], date=dt.date(2026, 10, 18), session="10PM",
        scheduled_at=timezone.now() + dt.timedelta(hours=1),
    )  # fmt: skip
    for fixture in (None, whole):
        with pytest.raises(MarketError, match="one match"):
            create_market(
                actor=staff, category=C.TOTAL_KILLS, title="x", season=game["season"],
                fixture=fixture, params={"line": 20}, odds={"yes": "2.00", "no": "2.00"},
                opens_at=timezone.now(), closes_at=timezone.now() + dt.timedelta(hours=1),
            )  # fmt: skip


def test_players_cant_bet_on_a_market_about_a_team_mate(game, staff, fans):
    m = market(game, staff, C.PLAYER_KILLS, player="Ace", line=4)
    Membership.objects.create(user=fans[0], team=game["teams"]["Alpha"])
    with pytest.raises(MarketError, match="your team") as err:
        bet(fans[0], m, outcome(m, "yes", game))
    assert err.value.code == "not_allowed"
    assert bet(fans[1], m, outcome(m, "yes", game)).stake == 100


# -- settling ------------------------------------------------------------------------------------


@pytest.mark.parametrize(("line", "winner"), [(21, "Over 20.5 kills"), (22, "Under 21.5 kills")])
def test_total_kills(game, staff, line, winner):
    winners, _, s = result(market(game, staff, C.TOTAL_KILLS, line=line), game)
    assert winners == [winner]  # 8 + 11 + 2 + 0 = 21
    assert s["evidence"]["total_kills"] == 21


@pytest.mark.parametrize(
    ("category", "teams", "line", "winner"),
    [
        (C.KILLS_HANDICAP, ["Bravo", "Alpha"], 3, "Bravo -2.5 kills"),  # 11 - 8 = 3
        (C.KILLS_HANDICAP, ["Bravo", "Alpha"], 4, "Alpha +3.5 kills"),
        (C.POINTS_HANDICAP, ["Alpha", "Charlie"], 10, "Alpha -9.5 points"),  # 20 - 10
        (C.POINTS_HANDICAP, ["Alpha", "Bravo"], 1, "Bravo +0.5 points"),  # 20 - 20: no lead
    ],
)
def test_handicaps(game, staff, category, teams, line, winner):
    winners, _, _ = result(market(game, staff, category, teams=teams, line=line), game)
    assert winners == [winner]


def test_handicap_with_a_team_missing_is_void(game, staff):
    m = market(game, staff, C.KILLS_HANDICAP, teams=["Alpha", "Echo"], line=2)
    assert result(m, game)[2]["kind"] == "VOID"


@pytest.mark.parametrize(
    ("team", "band"), [("Alpha", "1st"), ("Bravo", "2nd-3rd"), ("Delta", "4th-6th")]
)
def test_finishing_band(game, staff, team, band):
    winners, _, _ = result(market(game, staff, C.FINISH_BAND, team=team), game)
    assert winners == [f"{team}: {band}"]


def test_finishing_band_for_a_team_that_didnt_play_is_void(game, staff):
    assert result(market(game, staff, C.FINISH_BAND, team="Echo"), game)[2]["kind"] == "VOID"


def test_first_team_out_is_the_last_placed(game, staff):
    winners, voids, _ = result(
        market(game, staff, C.FIRST_OUT, teams=["Charlie", "Delta", "Echo"]), game
    )
    assert (winners, voids) == (["Delta"], ["Echo"])


def test_first_team_out_not_listed_loses_everyone(game, staff):
    winners, _, s = result(market(game, staff, C.FIRST_OUT, teams=["Alpha", "Bravo"]), game)
    assert winners == [] and "every bet loses" in s["note"]


def test_first_blood_ignores_a_team_mate_kill(game, staff):
    winners, _, s = result(market(game, staff, C.FIRST_BLOOD, teams=["Alpha", "Bravo"]), game)
    assert winners == ["Bravo"]
    assert s["evidence"]["first_blood"]["at_s"] == 40


def test_first_blood_without_timed_kills_is_void(game, staff):
    MatchEvent.objects.filter(kind=K.KILL).delete()
    m = market(game, staff, C.FIRST_BLOOD, teams=["Alpha", "Bravo"])
    assert result(m, game)[2]["kind"] == "VOID"


@pytest.mark.parametrize(("line", "code"), [(5, "yes"), (6, "no")])
def test_player_kills(game, staff, line, code):
    m = market(game, staff, C.PLAYER_KILLS, player="Ace", line=line)
    assert result(m, game)[0] == [outcome(m, code, game).label]


def test_player_who_didnt_play_is_void(game, staff):
    m = market(game, staff, C.PLAYER_KILLS, player="Echo", line=1)
    assert result(m, game)[2]["kind"] == "VOID"


def test_player_damage_and_missing_damage(game, staff):
    m = market(game, staff, C.PLAYER_DAMAGE, player="Ace", line=1300)
    assert result(m, game)[0] == ["Ace: over 1299.5 damage"]
    PlayerMatchResult.objects.update(damage_dealt=None)
    m = market(game, staff, C.PLAYER_DAMAGE, player="Ace", line=1300)
    s = suggest(Market.objects.get(pk=m.pk))
    assert s["kind"] == "VOID" and "no damage figures" in s["note"]


def test_player_head_to_head_and_tie(game, staff):
    assert result(market(game, staff, C.PLAYER_H2H, players=["Ace", "Bea"]), game)[0] == ["Bea"]
    tie = market(game, staff, C.PLAYER_H2H, players=["Ace", "Bo"])  # 5 v 5
    assert suggest(Market.objects.get(pk=tie.pk))["kind"] == "VOID"


def test_top_fragger_dead_heat_pays_half(game, staff, fans):
    PlayerMatchResult.objects.filter(display_name="Ace").update(kills=6)  # Ace and Bea: 6 each
    m = market(
        game, staff, C.TOP_FRAGGER, players=["Ace", "Bea", "Bo"],
        odds=None,
    )  # fmt: skip
    ace = bet(fans[0], m, outcome(m, "Ace", game), stake=100)
    bea = bet(fans[1], m, outcome(m, "Bea", game), stake=51)
    bo = bet(fans[2], m, outcome(m, "Bo", game), stake=100)
    winners, _, s = result(m, game)
    assert sorted(winners) == ["Ace", "Bea"] and s["dead_heat"] == 2
    done, _ = settle(Market.objects.get(pk=m.pk), actor=staff, winners=s["winners"])
    assert done.dead_heat == 2
    for b in (ace, bea, bo):
        b.refresh_from_db()
    assert (ace.status, ace.payout) == (B.WON, 100)  # 100 x 2.00 / 2
    assert (bea.status, bea.payout) == (B.WON, 51)
    assert (bo.status, bo.payout) == (B.LOST, 0)
    assert check_wallets() == []


def test_top_fragger_not_listed_and_absent_player(game, staff):
    winners, voids, _ = result(market(game, staff, C.TOP_FRAGGER, players=["Ace", "Echo"]), game)
    assert (winners, voids) == ([], ["Echo"])  # Bea has the most kills


def test_first_to_die_and_a_shared_moment(game, staff):
    m = market(game, staff, C.FIRST_DEATH, players=["Dee", "Cy", "Ace"])
    winners, _, s = result(m, game)
    assert winners == ["Dee"] and s["dead_heat"] == 1
    MatchEvent.objects.filter(kind=K.DEATH, game_time_s=300).update(game_time_s=90)
    s = suggest(Market.objects.get(pk=m.pk))
    assert s["dead_heat"] == 2 and len(s["winners"]) == 2


# -- odds and the API ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("category", "params"),
    [
        (C.TOTAL_KILLS, {"line": 20}),
        (C.KILLS_HANDICAP, {"teams": ["Bravo", "Delta"], "line": 4}),
        (C.POINTS_HANDICAP, {"teams": ["Alpha", "Delta"], "line": 6}),
        (C.FINISH_BAND, {"team": "Alpha"}),
        (C.FIRST_OUT, {"teams": ["Alpha", "Delta"]}),
        (C.FIRST_BLOOD, {"teams": ["Alpha", "Bravo"]}),
        (C.PLAYER_KILLS, {"player": "Bea", "line": 3}),
        (C.PLAYER_DAMAGE, {"player": "Bea", "line": 800}),
        (C.PLAYER_H2H, {"players": ["Bea", "Dee"]}),
        (C.TOP_FRAGGER, {"players": ["Bea", "Dee"]}),
        (C.FIRST_DEATH, {"players": ["Bea", "Dee"]}),
    ],
)
def test_suggested_odds_cover_every_new_market(game, staff, category, params):
    publish(game)
    t, p = game["teams"], game["players"]
    params = {
        k: ([(t if k == "teams" else p)[n].pk for n in v] if isinstance(v, list) else
            (t[v].pk if k == "team" else p[v].pk if k == "player" else v))
        for k, v in params.items()
    }  # fmt: skip
    got = suggest_odds(
        season=game["season"], category=category, params=params, fixture=game["fixture"]
    )
    assert set(got["odds"]) == {s["code"] for s in outcome_specs(category, params)}
    assert all(1 <= float(o) <= 500 for o in got["odds"].values())


def test_odds_reflect_history(game, staff):
    publish(game)
    p, t = game["players"], game["teams"]
    h2h = suggest_odds(
        season=game["season"], category=C.PLAYER_H2H,
        params={"players": [p["Bea"].pk, p["Dee"].pk]}, fixture=game["fixture"],
    )  # fmt: skip
    assert h2h["chances"][f"player:{p['Bea'].pk}"] > h2h["chances"][f"player:{p['Dee'].pk}"]
    blood = suggest_odds(
        season=game["season"], category=C.FIRST_BLOOD,
        params={"teams": [t["Bravo"].pk, t["Charlie"].pk]}, fixture=game["fixture"],
    )  # fmt: skip
    assert blood["chances"][f"team:{t['Bravo'].pk}"] > blood["chances"][f"team:{t['Charlie'].pk}"]
    assert [x["name"] for x in h2h["players"]] == ["Bea", "Dee"]


def test_api_shows_the_player_on_each_choice(game, staff, fans):
    m = market(game, staff, C.PLAYER_H2H, players=["Ace", "Bo"])
    data = as_user(fans[0]).get(f"/api/v1/predictions/markets/{m.pk}").json()
    players = [o["player"] for o in data["outcomes"]]
    assert [(x["name"], x["team"]["name"]) for x in players] == [("Ace", "Alpha"), ("Bo", "Bravo")]
