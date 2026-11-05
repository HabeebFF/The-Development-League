"""League players can predict on matches and sessions their team plays in, but not on anything
about them, their team or a team-mate: in a market with a choice per team or player only
those choices are closed; other markets about them are closed whole. A game UID waiting for
staff blocks all bets."""

import datetime as dt
import uuid

import pytest
from django.utils import timezone

from apps.accounts.models import Membership, PlayerClaim, StaffProfile
from apps.league.models import Player, ScoringRule, Season, Team
from apps.predictions.markets import MarketError, create_market, place_bet, transition
from apps.predictions.models import Fixture, Market
from apps.predictions.multiples import place_multiple

from .test_settlement import as_user, make_user

pytestmark = pytest.mark.django_db
S, C = Market.Status, Market.Category


@pytest.fixture(autouse=True)
def _on(settings):
    settings.PREDICTIONS_ENABLED = True


@pytest.fixture
def staff():
    user = make_user("staff@tdl.test")
    StaffProfile.objects.create(user=user)
    return user


@pytest.fixture
def lg():
    """Five league teams, one guest team, a session (8PM) with matches 1 and 2."""
    rule = ScoringRule.objects.create(name="R", placement_points={"1": 12})
    season = Season.objects.create(name="S9", slug="s9", scoring_rule=rule)
    teams = {n: Team.objects.create(name=n) for n in ("Alpha", "Bravo", "Charlie", "Delta", "Echo")}
    teams["Guest"] = Team.objects.create(name="Guest", is_league_member=False)
    later = timezone.now() + dt.timedelta(hours=2)
    day = dt.date(2026, 10, 20)
    common = {"season": season, "date": day, "session": "8PM", "scheduled_at": later}
    fixtures = {
        "session": Fixture.objects.create(**common),
        1: Fixture.objects.create(**common, match_number=1),
        2: Fixture.objects.create(**common, match_number=2),
    }
    players = {
        name: Player.objects.create(
            game_uid=7000 + i,
            current_name_raw=name,
            display_name=name,
            search_name=name.casefold(),
            current_team=teams[team] if team else None,
        )  # fmt: skip
        for i, (name, team) in enumerate((("Ace", "Alpha"), ("Ash", "Alpha"), ("Free", None)))
    }
    return {"season": season, "teams": teams, "fixtures": fixtures, "players": players}


def market(lg, by, category, fixture=None, **params):
    from apps.predictions.markets import outcome_specs

    t, p = lg["teams"], lg["players"]
    if "teams" in params:
        params["teams"] = [t[n].pk for n in params["teams"]]
    if "players" in params:
        params["players"] = [p[n].pk for n in params["players"]]
    now = timezone.now()
    m = create_market(
        actor=by,
        category=category,
        title=f"{category} market",
        season=lg["season"],
        fixture=lg["fixtures"][fixture] if fixture is not None else None,
        params=params,
        odds={s["code"]: "2.00" for s in outcome_specs(category, params)},
        opens_at=now - dt.timedelta(minutes=5),
        closes_at=now + dt.timedelta(hours=1),
    )
    transition(m, S.OPEN, actor=by)
    return m


def booyah(lg, staff, fixture=1, teams=("Alpha", "Bravo", "Charlie")):
    return market(lg, staff, C.BOOYAH, fixture, teams=list(teams))


def bet(user, m, choice=None, stake=50):
    """A bet on the choice labelled ``choice`` (a team or player name), else the first."""
    outcome = m.outcomes.get(label=choice) if choice else m.outcomes.first()
    return place_bet(
        user, market_id=m.pk, outcome_id=outcome.pk, stake=stake, client_key=uuid.uuid4()
    )[0]


def member(email, lg, team):
    user = make_user(email)
    Membership.objects.create(user=user, team=lg["teams"][team])
    return user


def refused(user, m, match="your own team or a team-mate", code="not_allowed", choice=None):
    with pytest.raises(MarketError, match=match) as err:
        bet(user, m, choice)
    assert err.value.code == code
    return err.value


def test_players_can_predict_on_their_own_match_but_not_their_team(lg, staff):
    lg["fixtures"][1].teams.set([lg["teams"][n] for n in ("Alpha", "Bravo", "Charlie")])
    m = booyah(lg, staff)
    alpha = member("alpha@tdl.test", lg, "Alpha")
    assert bet(alpha, m, "Bravo").stake == 50
    assert bet(alpha, m, "Charlie").stake == 50
    refused(alpha, m, choice="Alpha")
    assert bet(make_user("fan@tdl.test"), m, "Alpha").stake == 50


def test_the_whole_session_too(lg, staff):
    whole = market(lg, staff, C.SESSION_WINNER, "session", teams=["Alpha", "Bravo"])
    alpha = member("alpha@tdl.test", lg, "Alpha")
    assert bet(alpha, whole, "Bravo").stake == 50
    refused(alpha, whole, choice="Alpha")


def test_markets_about_their_team_are_closed_whole(lg, staff):
    alpha = member("alpha@tdl.test", lg, "Alpha")
    top3 = market(lg, staff, C.TOP_N, 1, team=lg["teams"]["Alpha"].pk, n=3)
    refused(alpha, top3, match="about your team", choice="Yes, Alpha top 3")
    h2h = market(lg, staff, C.H2H_PLACEMENT, 1, teams=["Alpha", "Bravo"])
    # Not even the other side of a head-to-head with their own team.
    refused(alpha, h2h, match="about your team", choice="Bravo")
    other = market(lg, staff, C.H2H_PLACEMENT, 1, teams=["Charlie", "Delta"])
    assert bet(alpha, other, "Charlie").stake == 50


def test_a_linked_player_without_a_membership_is_still_blocked(lg, staff):
    user = make_user("ace@tdl.test")
    Player.objects.filter(pk=lg["players"]["Ace"].pk).update(user=user)
    m = booyah(lg, staff, teams=("Alpha", "Bravo"))
    refused(user, m, choice="Alpha")
    assert bet(user, m, "Bravo").stake == 50


def test_season_markets_block_only_those_they_list(lg, staff):
    winner = market(lg, staff, C.OVERALL_WINNER, teams=["Alpha", "Bravo"])
    alpha = member("alpha@tdl.test", lg, "Alpha")
    refused(alpha, winner, choice="Alpha")
    assert bet(alpha, winner, "Bravo").stake == 50
    assert bet(member("echo@tdl.test", lg, "Echo"), winner).stake == 50

    frag = market(lg, staff, C.SEASON_FRAGGER, players=["Ash", "Free"])
    # Ash's team-mate can't pick Ash, but can pick Free; Free can't pick themselves.
    mate = member("alpha2@tdl.test", lg, "Alpha")
    refused(mate, frag, choice="Ash")
    assert bet(mate, frag, "Free").stake == 50
    free = make_user("free@tdl.test")
    Player.objects.filter(pk=lg["players"]["Free"].pk).update(user=free)
    refused(free, frag, match="pick yourself", choice="Free")
    assert bet(free, frag, "Ash").stake == 50
    kills = market(lg, staff, C.PLAYER_KILLS, 1, player=lg["players"]["Ash"].pk, line=3)
    refused(mate, kills, match="about your team")


def test_a_uid_waiting_for_staff_blocks_every_bet(lg, staff):
    user = make_user("new-player@tdl.test")
    PlayerClaim.objects.create(user=user, game_uid=123456)
    winner = market(lg, staff, C.OVERALL_WINNER, teams=["Alpha", "Bravo"])
    refused(user, winner, match="confirm your game UID", code="uid_pending")
    res = as_user(user).get(f"/api/v1/predictions/markets/{winner.pk}")
    assert "confirm your game UID" in res.json()["blocked"]
    res = as_user(user).post(
        "/api/v1/predictions/bets",
        {"market": winner.pk, "outcome": winner.outcomes.first().pk, "stake": 50,
         "client_key": str(uuid.uuid4())},
        format="json",
    )  # fmt: skip
    assert res.status_code == 403 and res.json()["code"] == "uid_pending"
    # Once staff have decided, the normal rules apply.
    PlayerClaim.objects.filter(user=user).update(status=PlayerClaim.Status.REJECTED)
    assert bet(user, winner).stake == 50


def test_markets_say_why_a_player_cant_predict(lg, staff):
    m = booyah(lg, staff)
    alpha = member("alpha@tdl.test", lg, "Alpha")
    rows = as_user(alpha).get("/api/v1/predictions/markets").json()["results"]
    assert rows[0]["blocked"] is None
    assert rows[0]["blocked_outcomes"] == [m.outcomes.get(label="Alpha").pk]
    top3 = market(lg, staff, C.TOP_N, 1, team=lg["teams"]["Alpha"].pk, n=3)
    res = as_user(alpha).get(f"/api/v1/predictions/markets/{top3.pk}").json()
    assert res["blocked"] == f"You can't predict on {top3.title}: it's about your team."
    assert res["blocked_outcomes"] == []
    rows = as_user(make_user("fan@tdl.test")).get("/api/v1/predictions/markets").json()
    assert rows["results"][0]["blocked"] is None


def test_multiples_follow_the_same_rules(lg, staff):
    lg["fixtures"][1].teams.set([lg["teams"]["Alpha"], lg["teams"]["Bravo"]])
    m1 = booyah(lg, staff, teams=("Alpha", "Bravo"))
    season = market(lg, staff, C.OVERALL_WINNER, teams=["Charlie", "Delta"])
    picks = [{"market": m.pk, "outcome": m.outcomes.first().pk} for m in (m1, season)]
    with pytest.raises(MarketError, match="your own team") as err:
        place_multiple(
            member("alpha@tdl.test", lg, "Alpha"), picks=picks, stake=50, client_key=uuid.uuid4()
        )
    assert err.value.code == "not_allowed"
    multiple, _ = place_multiple(
        member("echo@tdl.test", lg, "Echo"), picks=picks, stake=50, client_key=uuid.uuid4()
    )
    assert multiple.legs.count() == 2


def test_staff_set_a_fixture_lobby(lg, staff):
    f = lg["fixtures"][1]
    ids = [lg["teams"]["Alpha"].pk, lg["teams"]["Bravo"].pk]
    res = as_user(staff).patch(
        f"/api/v1/admin/predictions/fixtures/{f.pk}", {"teams": ids}, format="json"
    )
    assert res.status_code == 200, res.content
    assert sorted(res.json()["teams"]) == sorted(ids)


def test_repeat_predictions_on_one_choice_are_capped_in_total(lg, staff, settings):
    settings.PREDICTIONS_MAX_STAKE = 500
    m = booyah(lg, staff)
    fan = make_user("fan@tdl.test")
    assert bet(fan, m, "Bravo", stake=300).stake == 300
    assert bet(fan, m, "Bravo", stake=200).stake == 200
    with pytest.raises(MarketError, match="already have 500 coins on Bravo") as err:
        bet(fan, m, "Bravo", stake=10)
    assert err.value.code == "stake"
    # Other choices, and other people, have their own limit.
    assert bet(fan, m, "Charlie", stake=500).stake == 500
    assert bet(make_user("fan2@tdl.test"), m, "Bravo", stake=500).stake == 500


def test_the_cap_says_how_much_more_fits(lg, staff, settings):
    settings.PREDICTIONS_MAX_STAKE = 500
    m = booyah(lg, staff)
    fan = make_user("fan@tdl.test")
    bet(fan, m, "Bravo", stake=450)
    with pytest.raises(MarketError, match="add up to 50 more"):
        bet(fan, m, "Bravo", stake=100)
    assert bet(fan, m, "Bravo", stake=50).stake == 50
