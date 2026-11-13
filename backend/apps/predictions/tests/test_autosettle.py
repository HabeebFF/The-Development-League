"""Linking uploaded matches to fixtures and settling markets by themselves."""

import datetime as dt
import uuid
from unittest import mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import StaffProfile, User
from apps.league.models import Match, MatchDay, ScoringRule, Season, Stage, Team
from apps.predictions import auto, autosettle
from apps.predictions.markets import create_market, place_bet, transition
from apps.predictions.models import AutoSettings, Bet, Fixture, LedgerEntry, Market
from apps.predictions.services import check_wallets, wallet_for
from apps.predictions.settlement import correct
from apps.results.models import TeamMatchResult
from apps.results.standings import rebuild_season

pytestmark = pytest.mark.django_db
S, B, C = Market.Status, Bet.Status, Market.Category
PASSWORD = "a-Long-password-42"
# Alpha wins, Bravo 2nd, Charlie 3rd in every match unless a test says otherwise.
RESULTS = (("Alpha", 1, 9, 24), ("Bravo", 2, 8, 17), ("Charlie", 3, 5, 8))


@pytest.fixture(autouse=True)
def _on(settings):
    settings.PREDICTIONS_ENABLED = True


def make_user(email: str) -> User:
    return User.objects.create_user(email=email, password=PASSWORD, display_name=email[:5])


@pytest.fixture
def staff() -> User:
    user = make_user("staff@tdl.test")
    StaffProfile.objects.create(user=user)
    return user


@pytest.fixture
def fans():
    return [make_user(f"fan{i}@tdl.test") for i in range(3)]


@pytest.fixture
def night():
    """Three nights from now, 8PM: a lobby of Alpha, Bravo, Charlie and fixtures 1-5."""
    rule, _ = ScoringRule.objects.get_or_create(name="Test rule", defaults={"placement_points": {}})
    season = Season.objects.create(name="S1", slug="s1", scoring_rule=rule)
    stage = Stage.objects.create(season=season, name="Scrims")
    date = auto.today() + dt.timedelta(days=3)
    teams = {n: Team.objects.create(name=n) for n in ("Alpha", "Bravo", "Charlie", "Delta", "Echo")}
    start = auto.session_start(date, "8PM")
    whole = Fixture.objects.create(
        season=season, date=date, session="8PM", match_number=None, scheduled_at=start
    )
    whole.teams.set([teams[n].pk for n in ("Alpha", "Bravo", "Charlie")])
    fixtures = {
        n: Fixture.objects.create(
            season=season, date=date, session="8PM", match_number=n, scheduled_at=start
        )
        for n in range(1, 6)
    }
    return {
        "season": season,
        "stage": stage,
        "date": date,
        "start": start,
        "teams": teams,
        "whole": whole,
        "fixtures": fixtures,
    }


def upload(night, number, title="TDL DAY 20 8PM", results=RESULTS, started=None, day=None):
    """A published match, as an upload leaves it."""
    day = day or MatchDay.objects.get_or_create(
        stage=night["stage"], number=20 if "8PM" in title else 21, title=title,
        defaults={"date": night["date"]},
    )[0]  # fmt: skip
    started = started or night["start"] + dt.timedelta(minutes=5 + 22 * (number - 1))
    match = Match.objects.create(
        match_day=day, number=number, started_at=started, status=Match.Status.PUBLISHED
    )
    for name, place, kills, pts in results:
        TeamMatchResult.objects.create(
            match=match, team=night["teams"][name], in_game_name=name, placement=place,
            kills=kills, placement_points=pts - kills, kill_points=kills, total_points=pts,
        )  # fmt: skip
    return match


def market(night, staff, category=C.BOOYAH, number=1, teams=("Alpha", "Bravo", "Charlie"), **kw):
    ids = [night["teams"][t].pk for t in teams]
    fixture = night["whole"] if number is None else night["fixtures"][number]
    if category == C.TOP_N:
        params, odds = {"team": ids[0], "n": 3}, {"yes": "1.50", "no": "2.50"}
    else:
        params = {"teams": ids, **kw.pop("params", {})}
        odds = {f"team:{t}": "2.50" for t in ids}
    now = timezone.now()
    m = create_market(
        actor=staff,
        category=category,
        title=f"{category} {number}",
        season=night["season"],
        fixture=None if category == C.RANGE_WINNER else fixture,
        params=params,
        odds=odds,
        opens_at=now - dt.timedelta(minutes=5),
        closes_at=now + dt.timedelta(hours=1),
    )
    transition(m, S.OPEN, actor=staff)
    return m


def bet(user, m, team_or_code, stake=100):
    o = (
        m.outcomes.get(team=team_or_code)
        if isinstance(team_or_code, Team)
        else m.outcomes.get(code=team_or_code)
    )
    return place_bet(user, market_id=m.pk, outcome_id=o.pk, stake=stake, client_key=uuid.uuid4())[0]


def close(*markets):
    for m in markets:
        transition(m, S.CLOSED, actor=None)
        m.refresh_from_db()


def coins(user) -> int:
    return wallet_for(user).balance


def fresh(obj):
    obj.refresh_from_db()
    return obj


# -- linking and settling ------------------------------------------------------------------------


def test_upload_links_fixture_and_settles_bets(night, staff, fans):
    t = night["teams"]
    m = market(night, staff)
    win, lose = bet(fans[0], m, t["Alpha"]), bet(fans[1], m, t["Bravo"])
    close(m)

    match = upload(night, 1)
    report = autosettle.run(match.pk)

    assert fresh(night["fixtures"][1]).match_id == match.pk
    assert fresh(night["whole"]).match_day_id == match.match_day_id
    assert report["markets"]["settled"] == 1
    assert fresh(m).status == S.SETTLED
    assert (fresh(win).status, win.payout) == (B.WON, 250)
    assert fresh(lose).status == B.LOST
    assert coins(fans[0]) == 1150 and coins(fans[1]) == 900
    s = m.settlements.get()
    assert s.actor.email == auto.SYSTEM_EMAIL and s.reference == autosettle.AUTO_REFERENCE

    autosettle.run(match.pk)  # again: nothing pays twice
    assert LedgerEntry.objects.filter(bet=win, kind="PAYOUT").count() == 1
    assert check_wallets() == []


def test_upload_through_ingest_queues_settling(night):
    from apps.ingest.services import assemble

    with mock.patch("apps.predictions.tasks.auto_settle_task.delay") as delay:
        with pytest.MonkeyPatch.context() as mp:
            callbacks = []
            mp.setattr(assemble.transaction, "on_commit", callbacks.append)
            assemble._schedule_predictions(42)
            for cb in callbacks:
                cb()
    delay.assert_called_once_with(42)


def test_open_market_is_linked_but_waits_for_closing(night, staff, fans):
    m = market(night, staff)
    bet(fans[0], m, night["teams"]["Alpha"])
    match = upload(night, 1)
    autosettle.run(match.pk)
    assert fresh(night["fixtures"][1]).match_id == match.pk
    assert fresh(m).status == S.OPEN
    close(m)
    autosettle.run()
    assert fresh(m).status == S.SETTLED


def test_switched_off_does_nothing(night, staff):
    conf = AutoSettings.get()
    conf.settle_enabled = False
    conf.save()
    m = market(night, staff)
    close(m)
    match = upload(night, 1)
    assert autosettle.run(match.pk)["off"]
    assert fresh(night["fixtures"][1]).match_id is None
    assert fresh(m).status == S.CLOSED


def test_team_that_did_not_play_is_refunded(night, staff, fans):
    t = night["teams"]
    m = market(night, staff, teams=("Alpha", "Bravo", "Charlie"))
    refunded = bet(fans[0], m, t["Charlie"])
    close(m)
    match = upload(night, 1, results=RESULTS[:2])
    autosettle.run(match.pk)
    assert fresh(m).status == S.SETTLED
    assert fresh(refunded).status == B.VOID and coins(fans[0]) == 1000


def test_void_result_refunds_everyone(night, staff, fans):
    m = market(night, staff, C.TOP_N, teams=("Charlie",))
    b = bet(fans[0], m, "yes")
    close(m)
    match = upload(night, 1, results=RESULTS[:2])  # Charlie didn't play
    autosettle.run(match.pk)
    assert fresh(m).status == S.VOID
    assert fresh(b).status == B.VOID and coins(fans[0]) == 1000


# -- what's left for staff -----------------------------------------------------------------------


def test_match_day_without_session_is_not_linked(night, staff):
    m = market(night, staff)
    close(m)
    match = upload(night, 1, title="TDL DAY 20")
    autosettle.run(match.pk)
    f = fresh(night["fixtures"][1])
    assert f.match_id is None and "8PM or 10PM" in f.attention
    assert fresh(m).status == S.CLOSED
    assert autosettle.needs_you()["fixtures"][0]["id"] == f.pk


def test_match_outside_the_session_is_not_linked(night, staff):
    match = upload(night, 1, started=night["start"] + dt.timedelta(hours=5))
    market(night, staff)
    autosettle.run(match.pk)
    f = fresh(night["fixtures"][1])
    assert f.match_id is None and "outside the 8PM session" in f.attention


def test_fixture_linked_elsewhere_is_never_overwritten(night, staff):
    market(night, staff)
    other = upload(night, 1)
    night["fixtures"][1].match = other
    night["fixtures"][1].save()
    second_day = MatchDay.objects.create(
        stage=night["stage"], number=30, title="TDL DAY 20 8PM again", date=night["date"]
    )
    match = upload(night, 2, day=second_day)
    Match.objects.filter(pk=match.pk).update(number=1)
    autosettle.run(fresh(match).pk)
    f = fresh(night["fixtures"][1])
    assert f.match_id == other.pk and f.attention


def test_two_match_days_for_one_session_are_left_for_staff(night, staff):
    market(night, staff)
    MatchDay.objects.create(stage=night["stage"], number=31, title="HYDRA 8PM", date=night["date"])
    match = upload(night, 1)
    autosettle.run(match.pk)
    f = fresh(night["fixtures"][1])
    assert f.match_id is None and "More than one 8PM match day" in f.attention


def test_unsigned_team_playing_holds_the_market(night, staff, fans):
    """Charlie signed up but 'Echo' played: maybe the same team renamed. Don't refund."""
    m = market(night, staff)
    b = bet(fans[0], m, night["teams"]["Charlie"])
    close(m)
    match = upload(night, 1, results=(*RESULTS[:2], ("Echo", 3, 5, 8)))
    autosettle.run(match.pk)
    assert fresh(m).status == S.CLOSED
    assert "Charlie didn't play but Echo did" in m.attention
    assert fresh(b).status == B.PENDING


def test_staff_linking_by_hand_clears_the_note(night, staff):
    market(night, staff)
    match = upload(night, 1, title="TDL DAY 20")
    autosettle.run(match.pk)
    f = fresh(night["fixtures"][1])
    client = APIClient()
    client.force_authenticate(staff)
    url = f"/api/v1/admin/predictions/fixtures/{f.pk}"
    r = client.patch(url, {"match": match.pk}, format="json")
    assert r.status_code == 200, r.data
    assert fresh(f).attention == ""


def test_missing_upload_is_chased_after_the_session(night, staff):
    market(night, staff, number=5)
    autosettle.link_recent(now=night["start"] + dt.timedelta(hours=2))
    assert fresh(night["fixtures"][5]).attention == ""
    autosettle.link_recent(now=night["start"] + dt.timedelta(hours=7))
    assert "isn't uploaded" in fresh(night["fixtures"][5]).attention


def test_needs_you_is_staff_only(night, staff, fans):
    client = APIClient()
    client.force_authenticate(fans[0])
    assert client.get("/api/v1/admin/predictions/needs-you").status_code == 403
    client.force_authenticate(staff)
    r = client.get("/api/v1/admin/predictions/needs-you")
    assert r.status_code == 200 and r.data["on"] is True
    assert client.post("/api/v1/admin/predictions/needs-you").status_code == 200


# -- sessions, re-uploads, weeks -----------------------------------------------------------------


def test_session_market_waits_for_all_five_matches(night, staff, fans):
    t = night["teams"]
    m = market(night, staff, C.SESSION_WINNER, number=None)
    b = bet(fans[0], m, t["Alpha"])
    close(m)
    for n in range(1, 5):
        autosettle.run(upload(night, n).pk)
    assert fresh(m).status == S.CLOSED and m.attention == ""
    late = night["start"] + dt.timedelta(hours=7)
    autosettle.settle_recent(now=late)
    assert "Only 4 of 5" in fresh(m).attention
    upload(night, 5)
    autosettle.run()  # the standings aren't rebuilt yet: it waits
    assert fresh(m).status == S.CLOSED
    rebuild_season(night["season"])
    autosettle.run()
    assert fresh(m).status == S.SETTLED and m.attention == ""
    assert fresh(b).status == B.WON


def test_reupload_that_changes_the_result_is_flagged_not_paid(night, staff, fans):
    t = night["teams"]
    m = market(night, staff)
    win = bet(fans[0], m, t["Alpha"])
    close(m)
    match = upload(night, 1)
    autosettle.run(match.pk)
    assert fresh(win).status == B.WON

    # A fixed log: Bravo really won.
    TeamMatchResult.objects.filter(match=match, team=t["Alpha"]).update(placement=2)
    TeamMatchResult.objects.filter(match=match, team=t["Bravo"]).update(placement=1)
    fresh(match).save()  # the rebuild touches the match
    autosettle.run(match.pk)
    assert fresh(m).attention == autosettle.CHANGED
    assert coins(fans[0]) == 1150  # nothing taken back by itself
    assert autosettle.needs_you()["markets"][0]["id"] == m.pk

    bravo = m.outcomes.get(team=t["Bravo"]).pk
    correct(m, actor=staff, kind="SETTLE", reason="Fixed log", winners=[bravo])
    autosettle.run()
    assert fresh(m).attention == ""


def test_week_market_settles_once_the_week_is_uploaded(night, staff, fans):
    t = night["teams"]
    params = {"from": night["date"].isoformat(), "to": night["date"].isoformat()}
    m = market(night, staff, C.RANGE_WINNER, number=None, params=params)
    b = bet(fans[0], m, t["Alpha"])
    close(m)
    for n in range(1, 6):
        upload(night, n)
    rebuild_season(night["season"])
    autosettle.link_recent()
    during = night["start"] + dt.timedelta(hours=2)
    autosettle.settle_recent(now=during)
    assert fresh(m).status == S.CLOSED
    next_day = night["date"] + dt.timedelta(days=1)
    with mock.patch("django.utils.timezone.localdate", return_value=next_day):
        autosettle.settle_recent(now=night["start"] + dt.timedelta(hours=5))
    assert fresh(m).status == S.SETTLED and fresh(b).status == B.WON
