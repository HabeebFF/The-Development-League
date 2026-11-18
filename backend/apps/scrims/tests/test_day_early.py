"""Sign-up a day early (Habeeb, 2026-11-18): opens 8pm the night before, any linked player can
sign the team up, a DC fee with refunds, staff invites, and a full session locks."""

import datetime as dt
import itertools

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import Membership, StaffProfile
from apps.league.models import Player, Team
from apps.predictions.models import LedgerEntry
from apps.predictions.services import wallet_for
from apps.scrims import services as sv
from apps.scrims.models import Registration, ScrimLog, ScrimSettings

pytestmark = pytest.mark.django_db
R, A, K = Registration.Status, ScrimLog.Action, LedgerEntry.Kind

MONDAY = dt.date(2026, 11, 16)
TUESDAY = dt.date(2026, 11, 17)
WEDNESDAY = dt.date(2026, 11, 18)
THURSDAY = dt.date(2026, 11, 19)
uids = itertools.count(1000)


@pytest.fixture(autouse=True)
def rules():
    """The new defaults: 8pm the day before, 500 DC."""
    ScrimSettings.objects.update_or_create(
        pk=1, defaults={"opens_at": dt.time(20), "opens_days_before": 1, "fee": 500}
    )


@pytest.fixture
def clock(monkeypatch):
    def set_to(date, hour, minute=0):
        moment = dt.datetime.combine(date, dt.time(hour, minute), tzinfo=sv.local_tz())
        monkeypatch.setattr(sv, "now", lambda: moment)

    set_to(WEDNESDAY, 21)
    return set_to


def make_user(email, **kw):
    return get_user_model().objects.create_user(email=email, password="pw-123456", **kw)


@pytest.fixture
def staff():
    user = make_user("staff@tdl.test")
    StaffProfile.objects.create(user=user)
    return user


@pytest.fixture
def teams():
    return [Team.objects.create(name=f"Team {i:02}", slug=f"team-{i:02}") for i in range(1, 15)]


def linked_player(team, email=None, *, member=False):
    """An account linked to a game UID on ``team``."""
    user = make_user(email or f"p{next(uids)}@tdl.test")
    Player.objects.create(
        game_uid=next(uids), current_name_raw=user.email, display_name=user.email,
        search_name=user.email, current_team=team, user=user,
    )  # fmt: skip
    if member:
        Membership.objects.create(user=user, team=team, role=Membership.Role.PLAYER)
    return user


@pytest.fixture
def players(teams):
    """One linked player per team (1,000 DC each to start)."""
    return [linked_player(t) for t in teams]


def thursday(session="8PM"):
    return sv.get_session(THURSDAY, session)


def balance(user):
    return wallet_for(user).balance


def client_for(user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


def fill(teams, players, n=12, session="8PM"):
    return [sv.register(thursday(session), teams[i], players[i]) for i in range(n)]


# -- opening the day before ------------------------------------------------------------------------


def test_thursday_opens_wednesday_8pm_and_closes_thursday_as_before(clock, teams, players):
    clock(WEDNESDAY, 19, 59)
    assert sv.stage(THURSDAY, "8PM") == "soon"
    with pytest.raises(sv.ScrimError, match="opens at 8:00pm"):
        sv.register(thursday(), teams[0], players[0])
    clock(WEDNESDAY, 20)
    assert sv.register(thursday(), teams[0], players[0]).status == R.REGISTERED
    assert sv.register(thursday("10PM"), teams[1], players[1]).status == R.REGISTERED
    clock(THURSDAY, 18)
    assert sv.stage(THURSDAY, "8PM") == "closed"
    assert sv.stage(THURSDAY, "10PM") == "open"


def test_tuesday_opens_monday_8pm_and_says_which_day(clock, teams, players):
    clock(MONDAY - dt.timedelta(days=1), 13)  # Sunday
    with pytest.raises(sv.ScrimError, match="opens Monday at 8:00pm"):
        sv.register(sv.get_session(TUESDAY, "8PM"), teams[0], players[0])
    clock(MONDAY, 13)
    with pytest.raises(sv.ScrimError, match="opens at 8:00pm"):
        sv.register(sv.get_session(TUESDAY, "8PM"), teams[0], players[0])
    clock(MONDAY, 20)
    assert sv.register(sv.get_session(TUESDAY, "8PM"), teams[0], players[0])


def test_pages_show_tonight_and_the_next_night_once_it_opens(clock):
    clock(MONDAY, 19)
    assert sv.shown_nights() == [MONDAY]
    clock(MONDAY, 20)
    assert sv.shown_nights() == [MONDAY, TUESDAY]  # 10PM tonight still to come
    clock(MONDAY, 22)
    assert sv.shown_nights() == [TUESDAY]
    clock(WEDNESDAY, 13)
    assert sv.shown_nights() == [THURSDAY]  # no scrims tonight: the next night, opening later


def test_tonight_api_lists_both_nights(clock):
    clock(MONDAY, 20, 30)
    data = client_for().get("/api/v1/scrims/tonight").json()
    assert data["date"] == str(MONDAY)
    assert [n["date"] for n in data["nights"]] == [str(MONDAY), str(TUESDAY)]
    assert data["nights"][1]["sessions"][0]["stage"] == "open"
    assert data["nights"][1]["sessions"][0]["fee"] == 500


# -- who can sign up -------------------------------------------------------------------------------


def test_any_linked_player_on_the_team_can_sign_up(clock, teams, players):
    url = f"/api/v1/teams/{teams[0].slug}/scrims/{THURSDAY}/8PM/register"
    res = client_for(players[0]).post(url)
    assert res.status_code == 200, res.content
    row = Registration.objects.get(team=teams[0])
    assert row.registered_by == players[0] and row.paid_by == players[0]
    # The team page lists Thursday with the team's place.
    data = client_for(players[0]).get(f"/api/v1/teams/{teams[0].slug}/scrims").json()
    assert data["can_manage"] is True and data["fee"] == 500
    assert data["nights"][0]["sessions"][0]["mine"] == R.REGISTERED


def test_members_through_membership_count_too(clock, teams):
    other = linked_player(teams[1])  # linked, but on another team
    member = make_user("m@tdl.test")
    Player.objects.create(
        game_uid=next(uids), current_name_raw="m", display_name="m", search_name="m", user=member
    )
    Membership.objects.create(user=member, team=teams[0], role=Membership.Role.PLAYER)
    url = f"/api/v1/teams/{teams[0].slug}/scrims/{THURSDAY}/8PM/register"
    assert client_for(other).post(url).status_code == 403
    assert client_for(member).post(url).status_code == 200


def test_unlinked_members_and_strangers_cannot(clock, teams):
    unlinked = make_user("u@tdl.test")
    Membership.objects.create(user=unlinked, team=teams[0], role=Membership.Role.PLAYER)
    url = f"/api/v1/teams/{teams[0].slug}/scrims/{THURSDAY}/8PM/register"
    assert client_for(unlinked).post(url).status_code == 403
    assert client_for(make_user("x@tdl.test")).post(url).status_code == 403
    assert client_for().post(url).status_code in (401, 403)


def test_managers_still_can(clock, teams):
    boss = make_user("boss@tdl.test")
    Membership.objects.create(user=boss, team=teams[0], role=Membership.Role.MANAGER)
    url = f"/api/v1/teams/{teams[0].slug}/scrims/{THURSDAY}/8PM/register"
    assert client_for(boss).post(url).status_code == 200
    assert balance(boss) == 500


# -- the fee ---------------------------------------------------------------------------------------


def test_signing_up_costs_the_fee_once_per_session(clock, teams, players):
    sv.register(thursday(), teams[0], players[0])
    sv.register(thursday("10PM"), teams[0], players[0])
    assert balance(players[0]) == 0
    fees = LedgerEntry.objects.filter(kind=K.SCRIM_FEE, wallet__user=players[0])
    assert sorted(fees.values_list("amount", flat=True)) == [-500, -500]


def test_not_enough_dc_means_no_sign_up(clock, teams, players):
    conf = ScrimSettings.get()
    conf.fee = 5000
    conf.save()
    with pytest.raises(sv.ScrimError, match="costs 5,000 DC.*1000 DC"):
        sv.register(thursday(), teams[0], players[0])
    assert not Registration.objects.exists()
    assert balance(players[0]) == 1000


def test_staff_sign_up_free_and_a_free_setting_charges_nothing(clock, teams, players, staff):
    sv.register(thursday(), teams[0], staff)
    assert Registration.objects.get(team=teams[0]).fee_paid == 0
    conf = ScrimSettings.get()
    conf.fee = 0
    conf.save()
    sv.register(thursday(), teams[1], players[1])
    assert balance(players[1]) == 1000


def test_withdrawing_refunds(clock, teams, players):
    sv.register(thursday(), teams[0], players[0])
    sv.withdraw(thursday(), teams[0], players[0])
    assert balance(players[0]) == 1000
    assert LedgerEntry.objects.filter(kind=K.SCRIM_REFUND, amount=500).count() == 1
    assert ScrimLog.objects.filter(action=A.REFUNDED, team=teams[0]).exists()


def test_staff_removing_or_suspending_refunds_the_payer(clock, teams, players, staff):
    sv.register(thursday(), teams[0], players[0])
    sv.register(thursday("10PM"), teams[0], players[0])
    sv.staff_remove(thursday(), teams[0], staff)
    assert balance(players[0]) == 500
    sv.suspend(teams[0], staff, "no-show")
    assert balance(players[0]) == 1000


def test_fee_and_refund_are_not_earned_dc(clock, teams, players):
    from apps.dc.ranks import earned_by_user

    sv.register(thursday(), teams[0], players[0])
    sv.withdraw(thursday(), teams[0], players[0])
    assert earned_by_user().get(players[0].pk, 0) == 0


# -- full sessions lock ----------------------------------------------------------------------------


def test_twelfth_team_locks_the_session(clock, teams, players):
    fill(teams, players, 11)
    assert thursday().locked_at is None
    sv.register(thursday(), teams[11], players[11])
    assert thursday().locked_at is not None
    assert ScrimLog.objects.filter(action=A.FILLED, team=teams[11]).exists()
    # Playing teams can't withdraw now; latecomers can still join the waitlist (and leave it).
    with pytest.raises(sv.ScrimError, match="only staff"):
        sv.withdraw(thursday(), teams[0], players[0])
    assert sv.register(thursday(), teams[12], players[12]).status == R.WAITLIST
    sv.withdraw(thursday(), teams[12], players[12])
    assert balance(players[12]) == 1000


def test_staff_removing_from_a_locked_session_brings_in_the_waitlist(clock, teams, players, staff):
    fill(teams, players, 13)
    sv.staff_remove(thursday(), teams[0], staff)
    assert teams[12].pk in sv.lobby(thursday())
    assert len(sv.lobby(thursday())) == 12


def test_full_session_api_says_locked(clock, teams, players):
    fill(teams, players)
    data = client_for().get("/api/v1/scrims/tonight").json()
    assert data["nights"][0]["sessions"][0]["locked"] is True
    assert data["nights"][0]["sessions"][1]["locked"] is False


# -- staff invites ---------------------------------------------------------------------------------


def test_invite_holds_a_place_until_the_team_confirms_and_pays(clock, teams, players, staff):
    clock(WEDNESDAY, 13)  # before sign-up opens
    sv.staff_invite(thursday(), teams[0], staff, "you're in if you want it")
    assert sv.lobby(thursday()) == []  # not playing until confirmed
    url = f"/api/v1/teams/{teams[0].slug}/scrims/{THURSDAY}/8PM/register"
    data = client_for(players[0]).post(url).json()  # the same button confirms
    assert data["nights"][0]["sessions"][0]["mine"] == R.REGISTERED
    assert sv.lobby(thursday()) == [teams[0].pk]
    assert balance(players[0]) == 500
    assert ScrimLog.objects.filter(action=A.CONFIRMED, team=teams[0]).exists()


def test_invited_places_count_and_declining_frees_one(clock, teams, players, staff):
    fill(teams, players, 11)
    sv.staff_invite(thursday(), teams[11], staff)
    assert sv.register(thursday(), teams[12], players[12]).status == R.WAITLIST
    sv.withdraw(thursday(), teams[11], players[11])  # declines
    assert ScrimLog.objects.filter(action=A.DECLINED, team=teams[11]).exists()
    assert teams[12].pk in sv.lobby(thursday())
    assert thursday().locked_at is not None  # the waitlisted team filled it


def test_invite_rules(clock, teams, players, staff):
    sv.register(thursday(), teams[0], players[0])
    with pytest.raises(sv.ScrimError, match="already playing"):
        sv.staff_invite(thursday(), teams[0], staff)
    sv.staff_invite(thursday(), teams[1], staff)
    with pytest.raises(sv.ScrimError, match="already invited"):
        sv.staff_invite(thursday(), teams[1], staff)
    clock(THURSDAY, 18, 30)
    with pytest.raises(sv.ScrimError, match="closed"):
        sv.staff_invite(thursday(), teams[2], staff)


def test_staff_invite_api(clock, teams, staff):
    url = f"/api/v1/admin/scrims/{THURSDAY}/8PM/invite"
    res = client_for(staff).post(url, {"team": teams[0].pk, "note": "come"}, format="json")
    assert res.status_code == 200, res.content
    assert [e["team"]["id"] for e in res.json()["invited"]] == [teams[0].pk]


# -- when sign-up closes ---------------------------------------------------------------------------


def test_close_drops_invites_moves_waitlist_up_and_refunds_the_rest(clock, teams, players, staff):
    fill(teams, players, 10)
    sv.staff_invite(thursday(), teams[10], staff)
    sv.staff_invite(thursday(), teams[11], staff)
    sv.register(thursday(), teams[12], players[12])  # waitlist
    sv.register(thursday(), teams[13], players[13])  # waitlist
    sv.confirm(thursday(), teams[10], players[10])
    clock(THURSDAY, 18, 1)
    assert sv.wrap_due() == 1  # only the 8PM session exists
    lobby = sv.lobby(thursday())
    assert teams[11].pk not in lobby  # never confirmed
    assert teams[12].pk in lobby  # moved into the freed place, keeps its fee paid
    assert balance(players[12]) == 500
    assert Registration.objects.get(team=teams[13]).status == R.WAITLIST
    assert balance(players[13]) == 1000  # refunded
    assert ScrimLog.objects.filter(action=A.INVITE_EXPIRED, team=teams[11]).exists()
    # Once only.
    assert sv.wrap(thursday()) is False
    assert LedgerEntry.objects.filter(kind=K.SCRIM_REFUND).count() == 1


def test_teams_that_play_keep_their_fee_paid(clock, teams, players):
    sv.register(thursday(), teams[0], players[0])
    clock(THURSDAY, 21)
    sv.wrap_due()
    assert balance(players[0]) == 500


# -- settings --------------------------------------------------------------------------------------


def test_staff_settings_change_opening_and_fee(clock, staff):
    url = "/api/v1/admin/scrims/settings"
    res = client_for(staff).patch(
        url, {"opens_days_before": 0, "opens_at": "12:01", "fee": 1500}, format="json"
    )
    assert res.status_code == 200, res.content
    assert res.json()["fee"] == 1500
    assert sv.opens_at(THURSDAY).date() == THURSDAY
    # On the day, sign-up must still open before it closes.
    res = client_for(staff).patch(url, {"opens_at": "19:00"}, format="json")
    assert res.status_code == 400
    # The day before, any time works.
    res = client_for(staff).patch(url, {"opens_days_before": 1, "opens_at": "21:00"}, format="json")
    assert res.status_code == 200
    assert client_for(staff).patch(url, {"fee": -1}, format="json").status_code == 400
