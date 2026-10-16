"""Phase B markets: team kills, session winner, most Booyahs (dead heat), overall winner/top N."""

import datetime as dt
import uuid

import pytest
from django.utils import timezone

from apps.accounts.models import Membership, StaffProfile
from apps.league.models import Match, MatchDay, ScoringRule, Season, Stage, Team
from apps.predictions.markets import MarketError, create_market, place_bet, transition
from apps.predictions.models import Bet, Fixture, LedgerEntry, Market, Settlement, Wallet
from apps.predictions.services import check_wallets, wallet_for
from apps.predictions.settlement import correct, settle, suggest
from apps.results.models import TeamMatchResult
from apps.results.standings import rebuild_season

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
def fans():
    return [make_user(f"fan{i}@tdl.test") for i in range(3)]


@pytest.fixture
def session():
    """One 8PM session of two matches. Points: 12/9/8 for 1st/2nd/3rd plus 1 a kill.

    Match 1: Alpha 1st (3 kills), Bravo 2nd (10), Charlie 3rd (2).
    Match 2: Bravo 1st (4 kills), Alpha 2nd (5), Charlie 3rd (6).
    Session: Bravo 35 pts, Alpha 29, Charlie 24. Alpha and Bravo have one Booyah each.
    Delta is a league team that doesn't play.
    """
    rule = ScoringRule.objects.create(name="B rule", placement_points={"1": 12, "2": 9, "3": 8})
    season = Season.objects.create(name="S2", slug="s2", scoring_rule=rule)
    stage = Stage.objects.create(season=season, name="Scrims")
    day = MatchDay.objects.create(
        stage=stage, number=1, date=dt.date(2026, 10, 17), title="TDL DAY 1 8PM"
    )
    teams = {n: Team.objects.create(name=n) for n in ("Alpha", "Bravo", "Charlie", "Delta")}
    matches = []
    for number, lines in (
        (1, (("Alpha", 1, 3), ("Bravo", 2, 10), ("Charlie", 3, 2))),
        (2, (("Bravo", 1, 4), ("Alpha", 2, 5), ("Charlie", 3, 6))),
    ):
        match = Match.objects.create(match_day=day, number=number, status=Match.Status.PROCESSING)
        for name, place, kills in lines:
            TeamMatchResult.objects.create(
                match=match, team=teams[name], in_game_name=name, placement=place, kills=kills,
                placement_points=0, kill_points=0, total_points=0,
            )  # fmt: skip
        matches.append(match)
    later = timezone.now() + dt.timedelta(hours=1)
    whole = Fixture.objects.create(
        season=season, date=day.date, session="8PM", match_number=None, scheduled_at=later
    )
    first = Fixture.objects.create(
        season=season, date=day.date, session="8PM", match_number=1, scheduled_at=later
    )
    return {
        "season": season,
        "day": day,
        "matches": matches,
        "teams": teams,
        "session": whole,
        "match1": first,
    }


def market(session, by, category, *, fixture="session", **params):
    t = session["teams"]
    if category in (C.TEAM_KILLS, C.OVERALL_TOP_N):
        odds = {"yes": "1.80", "no": "2.00"}
        params = {"team": t[params.pop("team", "Bravo")].pk, **params}
    else:
        names = params.pop("teams", ("Alpha", "Bravo", "Charlie", "Delta"))
        params = {"teams": [t[n].pk for n in names]}
        odds = {
            f"team:{t[n].pk}": o
            for n, o in zip(names, ("3.00", "2.50", "4.00", "9.00"), strict=False)
        }
    now = timezone.now()
    m = create_market(
        actor=by,
        category=category,
        title=f"{category} market",
        season=session["season"],
        fixture=session[fixture] if fixture else None,
        params=params,
        odds=odds,
        opens_at=now - dt.timedelta(minutes=5),
        closes_at=now + dt.timedelta(hours=1),
    )
    transition(m, S.OPEN, actor=by)
    return m


def pick(m, code_or_name, session):
    if code_or_name in session["teams"]:
        return m.outcomes.get(team=session["teams"][code_or_name])
    return m.outcomes.get(code=code_or_name)


def bet(user, m, outcome, stake=100):
    return place_bet(
        user, market_id=m.pk, outcome_id=outcome.pk, stake=stake, client_key=uuid.uuid4()
    )[0]


def publish(session, *, link_day=True, link_match=True):
    Match.objects.filter(pk__in=[m.pk for m in session["matches"]]).update(
        status=Match.Status.PUBLISHED
    )
    if link_day:
        session["session"].match_day = session["day"]
        session["session"].save()
    if link_match:
        session["match1"].match = session["matches"][0]
        session["match1"].save()
    rebuild_season(session["season"])


def close(m, by):
    transition(m, S.CLOSED, actor=by)
    m.refresh_from_db()


# -- creating -----------------------------------------------------------------------------------


def test_team_kills_offers_a_pair_with_no_gap(session, staff):
    m = market(session, staff, C.TEAM_KILLS, fixture="match1", line=10)
    labels = [o.label for o in m.outcomes.order_by("sort")]
    assert labels == ["Bravo: 10 or more kills", "Bravo: 9 or fewer kills"]


@pytest.mark.parametrize("line", [0, 61, "10", True, 2.5, None])
def test_team_kills_line_must_be_a_whole_number(session, staff, line):
    with pytest.raises(MarketError, match="kills line"):
        market(session, staff, C.TEAM_KILLS, fixture="match1", line=line)


@pytest.mark.parametrize(
    "category,fixture,message",
    [
        (C.TEAM_KILLS, "session", "one match"),
        (C.SESSION_WINNER, "match1", "whole-session"),
        (C.MOST_BOOYAHS, None, "whole-session"),
        (C.OVERALL_WINNER, "session", "whole season"),
    ],
)
def test_each_market_needs_the_right_kind_of_fixture(session, staff, category, fixture, message):
    kw = {"line": 10} if category == C.TEAM_KILLS else {}
    with pytest.raises(MarketError, match=message):
        market(session, staff, category, fixture=fixture, **kw)


# -- team kills ---------------------------------------------------------------------------------


@pytest.mark.parametrize("line,won", [(10, "yes"), (11, "no")])
def test_team_kills_settles_on_the_line(session, staff, fans, line, won):
    m = market(session, staff, C.TEAM_KILLS, fixture="match1", line=line)
    yes = bet(fans[0], m, pick(m, "yes", session))
    no = bet(fans[1], m, pick(m, "no", session))
    publish(session)
    close(m, staff)
    s = suggest(m)
    assert s["winners"] == [pick(m, won, session).pk]
    settle(m, actor=staff, winners=s["winners"])
    yes.refresh_from_db()
    no.refresh_from_db()
    assert (yes.status, no.status) == ((B.WON, B.LOST) if won == "yes" else (B.LOST, B.WON))
    assert check_wallets() == []


def test_team_kills_refunds_when_the_team_does_not_play(session, staff, fans):
    m = market(session, staff, C.TEAM_KILLS, fixture="match1", team="Delta", line=5)
    bet(fans[0], m, pick(m, "yes", session))
    publish(session)
    close(m, staff)
    assert suggest(m)["kind"] == "VOID"


# -- session winner -----------------------------------------------------------------------------


def test_session_market_waits_for_the_day_link_publishing_and_standings(session, staff):
    m = market(session, staff, C.SESSION_WINNER)
    close(m, staff)
    with pytest.raises(MarketError, match="match day"):
        suggest(m)
    session["session"].match_day = session["day"]
    session["session"].save()
    m = Market.objects.get(pk=m.pk)
    with pytest.raises(MarketError, match="need publishing"):
        suggest(m)
    Match.objects.filter(match_day=session["day"]).update(status=Match.Status.PUBLISHED)
    with pytest.raises(MarketError, match="standings"):
        suggest(m)  # published, but the standings haven't been rebuilt yet
    rebuild_season(session["season"])
    assert suggest(m)["kind"] == "SETTLE"


def test_session_winner_pays_the_top_team_and_refunds_teams_that_did_not_play(
    session,
    staff,
    fans,
):
    m = market(session, staff, C.SESSION_WINNER)
    bravo = bet(fans[0], m, pick(m, "Bravo", session), stake=100)
    alpha = bet(fans[1], m, pick(m, "Alpha", session), stake=100)
    delta = bet(fans[2], m, pick(m, "Delta", session), stake=50)
    publish(session)
    close(m, staff)
    s = suggest(m)
    assert s["winners"] == [pick(m, "Bravo", session).pk]
    assert s["voids"] == [pick(m, "Delta", session).pk]
    assert s["dead_heat"] == 1
    assert s["evidence"]["standings"][0]["name"] == "Bravo"
    settle(m, actor=staff, winners=s["winners"], voids=s["voids"])
    for b in (bravo, alpha, delta):
        b.refresh_from_db()
    assert (bravo.status, bravo.payout) == (B.WON, 250)
    assert (alpha.status, alpha.payout) == (B.LOST, 0)
    assert (delta.status, delta.payout) == (B.VOID, 50)
    assert wallet_for(fans[0]).balance == 1000 - 100 + 250
    assert check_wallets() == []


def test_session_bets_placed_after_the_first_match_started_are_refunded(session, staff, fans):
    m = market(session, staff, C.SESSION_WINNER)
    late = bet(fans[0], m, pick(m, "Bravo", session), stake=100)
    Match.objects.filter(pk=session["matches"][0].pk).update(
        started_at=late.placed_at - dt.timedelta(seconds=1)
    )
    publish(session)
    close(m, staff)
    s = suggest(m)
    settle(m, actor=staff, winners=s["winners"], voids=s["voids"])
    late.refresh_from_db()
    assert (late.status, late.payout) == (B.VOID, 100)


# -- most Booyahs and dead heats ----------------------------------------------------------------


def test_most_booyahs_tie_is_a_dead_heat(session, staff, fans):
    m = market(session, staff, C.MOST_BOOYAHS, teams=("Alpha", "Bravo", "Charlie"))
    alpha = bet(fans[0], m, pick(m, "Alpha", session), stake=100)  # 3.00
    bravo = bet(fans[1], m, pick(m, "Bravo", session), stake=101)  # 2.50
    charlie = bet(fans[2], m, pick(m, "Charlie", session), stake=100)
    publish(session)
    close(m, staff)
    s = suggest(m)
    assert sorted(s["winners"]) == sorted(
        [pick(m, "Alpha", session).pk, pick(m, "Bravo", session).pk]
    )
    assert s["dead_heat"] == 2
    done, _ = settle(m, actor=staff, winners=s["winners"])
    assert done.dead_heat == 2
    for b in (alpha, bravo, charlie):
        b.refresh_from_db()
    assert (alpha.status, alpha.payout) == (B.WON, 150)  # 100 x 3.00 / 2
    assert (bravo.status, bravo.payout) == (B.WON, 126)  # 101 x 2.50 / 2 = 126.25, rounded down
    assert (charlie.status, charlie.payout) == (B.LOST, 0)
    assert check_wallets() == []


def test_settling_a_tie_as_one_winner_needs_a_reason(session, staff, fans):
    m = market(session, staff, C.MOST_BOOYAHS, teams=("Alpha", "Bravo", "Charlie"))
    publish(session)
    close(m, staff)
    alpha = pick(m, "Alpha", session).pk
    with pytest.raises(MarketError, match="reason") as err:
        settle(m, actor=staff, winners=[alpha], dead_heat=1)
    assert err.value.code == "override"
    done, _ = settle(m, actor=staff, winners=[alpha], dead_heat=1, override_reason="Bravo DQ'd")
    assert done.dead_heat == 1


def test_only_team_winner_markets_can_dead_heat(session, staff):
    m = market(session, staff, C.TEAM_KILLS, fixture="match1", line=10)
    publish(session)
    close(m, staff)
    with pytest.raises(MarketError, match="dead heat"):
        settle(
            m, actor=staff, winners=[pick(m, "yes", session).pk], dead_heat=2, override_reason="x"
        )


def test_dead_heat_cannot_be_smaller_than_the_winners(session, staff):
    m = market(session, staff, C.MOST_BOOYAHS, teams=("Alpha", "Bravo", "Charlie"))
    publish(session)
    close(m, staff)
    both = [pick(m, "Alpha", session).pk, pick(m, "Bravo", session).pk]
    with pytest.raises(MarketError, match="smaller"):
        settle(m, actor=staff, winners=both, dead_heat=1, override_reason="x")


def test_correcting_a_dead_heat_pays_the_difference(session, staff, fans):
    m = market(session, staff, C.MOST_BOOYAHS, teams=("Alpha", "Bravo", "Charlie"))
    alpha = bet(fans[0], m, pick(m, "Alpha", session), stake=100)
    bravo = bet(fans[1], m, pick(m, "Bravo", session), stake=100)
    publish(session)
    close(m, staff)
    settle(m, actor=staff, winners=suggest(m)["winners"])  # 150 and 125
    done, _ = correct(
        m,
        actor=staff,
        kind=Settlement.Kind.SETTLE,
        reason="Bravo's Booyah was a scoring error",
        winners=[pick(m, "Alpha", session).pk],
        dead_heat=1,
        key=str(uuid.uuid4()),
    )
    assert (done.version, done.dead_heat) == (2, 1)
    alpha.refresh_from_db()
    bravo.refresh_from_db()
    assert (alpha.status, alpha.payout) == (B.WON, 300)
    assert (bravo.status, bravo.payout) == (B.LOST, 0)
    amounts = dict(LedgerEntry.objects.filter(kind="CORRECTION").values_list("bet_id", "amount"))
    assert amounts == {alpha.pk: 150, bravo.pk: -125}
    assert wallet_for(fans[0]).balance == 1000 - 100 + 300
    assert check_wallets() == []


def test_draft_matches_are_left_out_of_a_session(session, staff):
    left = Match.objects.create(match_day=session["day"], number=3, status=Match.Status.DRAFT)
    m = market(session, staff, C.SESSION_WINNER)
    publish(session)
    close(m, staff)
    s = suggest(m)
    assert s["evidence"]["left_out"] == [left.pk]
    assert len(s["evidence"]["matches"]) == 2


# -- overall ------------------------------------------------------------------------------------


def test_overall_winner_reads_the_season_table(session, staff, fans):
    m = market(session, staff, C.OVERALL_WINNER, fixture=None, teams=("Alpha", "Bravo"))
    b = bet(fans[0], m, pick(m, "Bravo", session), stake=200)
    publish(session)
    close(m, staff)
    s = suggest(m)
    assert s["winners"] == [pick(m, "Bravo", session).pk]
    assert s["evidence"]["matches_counted"] == 2
    settle(m, actor=staff, winners=s["winners"])
    b.refresh_from_db()
    assert (b.status, b.payout) == (B.WON, 500)


@pytest.mark.parametrize(
    "team,n,won", [("Charlie", 3, "yes"), ("Alpha", 3, "yes"), ("Delta", 3, None)]
)
def test_overall_top_n(session, staff, team, n, won):
    m = market(session, staff, C.OVERALL_TOP_N, fixture=None, team=team, n=n)
    publish(session)
    close(m, staff)
    s = suggest(m)
    if won is None:
        assert s["kind"] == "VOID"  # the team never played
    else:
        assert s["winners"] == [pick(m, won, session).pk]


# -- API ----------------------------------------------------------------------------------------


def test_staff_link_a_session_fixture_to_its_match_day(session, staff):
    api = as_user(staff)
    other = MatchDay.objects.create(
        stage=session["day"].stage, number=2, date=session["day"].date, title="TDL DAY 1 10PM"
    )
    url = f"/api/v1/admin/predictions/fixtures/{session['session'].pk}"
    rows = api.get(f"{url}/candidate-days").json()
    assert [r["id"] for r in rows] == [session["day"].pk, other.pk]
    assert rows[0]["likely"] and rows[0]["matches"] == 2
    res = api.patch(url, {"match_day": session["day"].pk}, format="json")
    assert res.status_code == 200, res.content
    assert Fixture.objects.get(pk=session["session"].pk).match_day_id == session["day"].pk


def test_settle_through_the_api_with_a_dead_heat(session, staff, fans):
    m = market(session, staff, C.MOST_BOOYAHS, teams=("Alpha", "Bravo", "Charlie"))
    publish(session)
    close(m, staff)
    api = as_user(staff)
    url = f"/api/v1/admin/predictions/markets/{m.pk}"
    s = api.get(f"{url}/suggested-result").json()
    assert s["dead_heat"] == 2
    res = api.post(f"{url}/settle", {"winners": s["winners"], "dead_heat": 2}, format="json")
    assert res.status_code == 201, res.content
    assert res.json()["dead_heat"] == 2


def test_staff_list_season_long_markets(session, staff):
    overall = market(session, staff, C.OVERALL_WINNER, fixture=None, teams=("Alpha", "Bravo"))
    market(session, staff, C.SESSION_WINNER)
    rows = as_user(staff).get("/api/v1/admin/predictions/markets?fixture=none").json()["results"]
    assert [r["id"] for r in rows] == [overall.pk]


def test_player_cannot_bet_on_own_team_in_session_market(session, staff):
    fan = make_user("bravo-player@tdl.test")
    Membership.objects.create(user=fan, team=session["teams"]["Bravo"])
    m = market(session, staff, C.SESSION_WINNER)
    with pytest.raises(MarketError, match="your team"):
        bet(fan, m, pick(m, "Alpha", session))


# -- nobody listed wins, and the simulation ------------------------------------------------------


def test_market_settles_when_the_winner_is_not_a_choice(session, staff, fans):
    m = market(session, staff, C.SESSION_WINNER, teams=("Alpha", "Charlie"))
    lost = bet(fans[0], m, pick(m, "Alpha", session))
    publish(session)
    close(m, staff)
    s = suggest(m)  # Bravo won the session but isn't a choice
    assert (s["kind"], s["winners"], s["voids"]) == ("SETTLE", [], [])
    settle(m, actor=staff, winners=[], voids=[])
    lost.refresh_from_db()
    assert (lost.status, lost.payout) == (B.LOST, 0)


def test_simulation_checks_every_coin_and_saves_nothing():
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    call_command(
        "simulate_predictions", users=6, teams=6, matches=2, sessions=1, bets=4, seed=3, stdout=out
    )
    report = out.getvalue()
    assert "Every wallet matches its ledger" in report
    assert "rolled back" in report
    assert not Team.objects.filter(name__startswith="Sim ").exists()
    assert not Wallet.objects.exists()
