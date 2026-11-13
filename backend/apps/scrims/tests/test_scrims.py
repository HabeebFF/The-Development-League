"""Scrim registration: sign-up times, places and waitlist, suspensions, staff changes, API."""

import datetime as dt

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import Membership, StaffProfile
from apps.league.models import Team
from apps.scrims import services as sv
from apps.scrims.models import Registration, ScrimLog, ScrimSettings

pytestmark = pytest.mark.django_db
R, A = Registration.Status, ScrimLog.Action

MONDAY = dt.date(2026, 11, 16)
WEDNESDAY = dt.date(2026, 11, 18)


@pytest.fixture
def clock(monkeypatch):
    """Set the Lagos time: ``clock(MONDAY, 12, 1)``."""

    def set_to(date, hour, minute=0):
        moment = dt.datetime.combine(date, dt.time(hour, minute), tzinfo=sv.local_tz())
        monkeypatch.setattr(sv, "now", lambda: moment)

    set_to(MONDAY, 13)
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


@pytest.fixture
def manager(teams):
    user = make_user("manager@tdl.test")
    Membership.objects.create(user=user, team=teams[0], role=Membership.Role.MANAGER)
    return user


def client_for(user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


def eight():
    return sv.get_session(MONDAY, "8PM")


# -- times -----------------------------------------------------------------------------------------


def test_sign_up_opens_at_1201(clock, teams, manager):
    clock(MONDAY, 12, 0)
    with pytest.raises(sv.ScrimError, match="opens at 12:01pm"):
        sv.register(eight(), teams[0], manager)
    clock(MONDAY, 12, 1)
    assert sv.register(eight(), teams[0], manager).status == R.REGISTERED
    # Both sessions open together.
    assert sv.register(sv.get_session(MONDAY, "10PM"), teams[0], manager).status == R.REGISTERED


def test_sign_up_closes_6pm_for_8pm_and_8pm_for_10pm(clock, teams, manager):
    clock(MONDAY, 18, 0)
    with pytest.raises(sv.ScrimError, match="closed"):
        sv.register(eight(), teams[0], manager)
    sv.register(sv.get_session(MONDAY, "10PM"), teams[0], manager)
    clock(MONDAY, 20, 0)
    with pytest.raises(sv.ScrimError, match="closed"):
        sv.register(sv.get_session(MONDAY, "10PM"), teams[1], manager)
    assert sv.stage(MONDAY, "8PM") == "started"
    assert sv.stage(MONDAY, "10PM") == "closed"


def test_only_monday_tuesday_thursday_friday(clock, teams, manager):
    clock(WEDNESDAY, 13)
    with pytest.raises(sv.ScrimError, match="no scrims"):
        sv.register(sv.get_session(WEDNESDAY, "8PM"), teams[0], manager)
    nights = [MONDAY + dt.timedelta(days=d) for d in range(7)]
    assert [sv.is_scrim_night(d) for d in nights] == [1, 1, 0, 1, 1, 0, 0]
    assert sv.next_scrim_night(start=WEDNESDAY) == MONDAY + dt.timedelta(days=3)


def test_skipped_night_has_no_sign_up(clock, teams, manager):
    conf = ScrimSettings.get()
    conf.skip_dates = [MONDAY.isoformat()]
    conf.save()
    with pytest.raises(sv.ScrimError, match="no scrims"):
        sv.register(eight(), teams[0], manager)


# -- places and waitlist ---------------------------------------------------------------------------


def test_twelve_places_then_waitlist_in_order(clock, teams, manager):
    rows = [sv.register(eight(), t, manager) for t in teams[:14]]
    assert [r.status for r in rows] == [R.REGISTERED] * 12 + [R.WAITLIST] * 2
    assert sv.lobby(eight()) == [t.pk for t in teams[:12]]


def test_withdraw_moves_first_waitlisted_team_up(clock, teams, manager):
    for t in teams[:14]:
        sv.register(eight(), t, manager)
    sv.withdraw(eight(), teams[3], manager)
    assert teams[12].pk in sv.lobby(eight())
    assert Registration.objects.get(team=teams[13]).status == R.WAITLIST
    assert ScrimLog.objects.filter(team=teams[12], action=A.MOVED_UP).exists()


def test_cannot_register_twice(clock, teams, manager):
    sv.register(eight(), teams[0], manager)
    with pytest.raises(sv.ScrimError, match="already signed up"):
        sv.register(eight(), teams[0], manager)


def test_withdraw_only_while_open(clock, teams, manager):
    sv.register(eight(), teams[0], manager)
    clock(MONDAY, 18, 30)
    with pytest.raises(sv.ScrimError, match="only staff"):
        sv.withdraw(eight(), teams[0], manager)


def test_waitlist_does_not_move_up_after_close(clock, teams, manager, staff):
    for t in teams[:13]:
        sv.register(eight(), t, manager)
    clock(MONDAY, 18, 30)
    sv.staff_remove(eight(), teams[0], staff)
    assert len(sv.lobby(eight())) == 11
    assert Registration.objects.get(team=teams[12]).status == R.WAITLIST


def test_more_places_move_waitlist_up(clock, teams, manager, staff):
    for t in teams[:14]:
        sv.register(eight(), t, manager)
    sv.set_max_teams(eight(), 13, staff)
    assert len(sv.lobby(eight())) == 13
    sv.set_max_teams(eight(), 10, staff)  # fewer places never push a team out
    assert len(sv.lobby(eight())) == 13


# -- staff -----------------------------------------------------------------------------------------


def test_staff_add_past_cap_after_close_and_for_suspended(clock, teams, manager, staff):
    for t in teams[:12]:
        sv.register(eight(), t, manager)
    sv.suspend(teams[13], staff, "late twice")
    clock(MONDAY, 19)
    sv.staff_add(eight(), teams[13], staff, "replacement")
    assert len(sv.lobby(eight())) == 13
    row = Registration.objects.get(team=teams[13])
    assert row.by_staff and row.status == R.REGISTERED
    assert ScrimLog.objects.get(team=teams[13], action=A.STAFF_ADDED).note == "replacement"


def test_staff_add_puts_waitlisted_team_in(clock, teams, manager, staff):
    for t in teams[:13]:
        sv.register(eight(), t, manager)
    sv.staff_add(eight(), teams[12], staff)
    assert Registration.objects.get(team=teams[12]).status == R.REGISTERED
    with pytest.raises(sv.ScrimError, match="already playing"):
        sv.staff_add(eight(), teams[12], staff)


def test_staff_can_change_any_date(clock, teams, staff):
    later = MONDAY + dt.timedelta(days=7)
    sv.staff_add(sv.get_session(later, "10PM"), teams[0], staff)
    sv.staff_remove(sv.get_session(later, "10PM"), teams[0], staff)
    assert sv.lobby(sv.get_session(later, "10PM")) == []


# -- suspensions -----------------------------------------------------------------------------------


def test_suspended_team_cannot_register_until_unsuspended(clock, teams, manager, staff):
    sv.suspend(teams[0], staff, "No-show")
    with pytest.raises(sv.ScrimError, match="suspended.*No-show"):
        sv.register(eight(), teams[0], manager)
    with pytest.raises(sv.ScrimError, match="already suspended"):
        sv.suspend(teams[0], staff)
    sv.unsuspend(teams[0], staff)
    assert sv.register(eight(), teams[0], manager).status == R.REGISTERED
    actions = set(ScrimLog.objects.filter(team=teams[0]).values_list("action", flat=True))
    assert {A.SUSPENDED, A.UNSUSPENDED, A.REGISTERED} <= actions


def test_suspension_with_end_date_lapses(clock, teams, manager, staff):
    sv.suspend(teams[0], staff, until=MONDAY)
    assert sv.active_suspension(teams[0])
    clock(MONDAY + dt.timedelta(days=1), 13)
    assert sv.active_suspension(teams[0]) is None
    sv.register(sv.get_session(MONDAY + dt.timedelta(days=1), "8PM"), teams[0], manager)


def test_suspending_removes_from_tonight_and_moves_waitlist_up(clock, teams, manager, staff):
    for t in teams[:13]:
        sv.register(eight(), t, manager)
    sv.register(sv.get_session(MONDAY, "10PM"), teams[0], manager)
    sv.suspend(teams[0], staff)
    assert teams[0].pk not in sv.lobby(eight())
    assert sv.lobby(sv.get_session(MONDAY, "10PM")) == []
    assert teams[12].pk in sv.lobby(eight())
    assert ScrimLog.objects.filter(team=teams[0], action=A.SUSPENDED_OUT).count() == 2


def test_suspending_leaves_a_started_session_alone(clock, teams, manager, staff):
    sv.register(eight(), teams[0], manager)
    sv.register(sv.get_session(MONDAY, "10PM"), teams[0], manager)
    clock(MONDAY, 20, 30)
    sv.suspend(teams[0], staff)
    assert sv.lobby(eight()) == [teams[0].pk]
    assert sv.lobby(sv.get_session(MONDAY, "10PM")) == []


# -- predictions hook ------------------------------------------------------------------------------


def test_lobby_changed_is_sent_when_playing_teams_change(
    clock, teams, manager, staff, django_capture_on_commit_callbacks
):
    seen = []

    def heard(sender, scrim, **kw):
        seen.append(str(scrim))

    sv.lobby_changed.connect(heard)
    try:
        with django_capture_on_commit_callbacks(execute=True):
            for t in teams[:13]:
                sv.register(eight(), t, manager)
        assert len(seen) == 12  # the 13th joined the waitlist: nobody new is playing
        seen.clear()
        with django_capture_on_commit_callbacks(execute=True):
            sv.staff_remove(eight(), teams[0], staff)
        assert seen == [f"{MONDAY} 8PM"]
    finally:
        sv.lobby_changed.disconnect(heard)


# -- API -------------------------------------------------------------------------------------------


def test_only_team_managers_register(clock, teams, manager):
    player = make_user("player@tdl.test")
    Membership.objects.create(user=player, team=teams[0], role=Membership.Role.PLAYER)
    url = f"/api/v1/teams/{teams[0].slug}/scrims/{MONDAY}/8PM/register"
    assert client_for(player).post(url).status_code == 403
    assert client_for(make_user("x@tdl.test")).post(url).status_code == 403
    assert client_for().post(url).status_code in (401, 403)
    res = client_for(manager).post(url)
    assert res.status_code == 200, res.data
    eight_pm = res.data["sessions"][0]
    assert eight_pm["mine"] == R.REGISTERED and eight_pm["stage"] == "open"
    # Players can see it.
    seen = client_for(player).get(f"/api/v1/teams/{teams[0].slug}/scrims").data
    assert seen["sessions"][0]["mine"] == R.REGISTERED and seen["can_manage"] is False


def test_api_shows_rule_errors(clock, teams, manager, staff):
    sv.suspend(teams[0], staff, "No-show")
    res = client_for(manager).post(f"/api/v1/teams/{teams[0].slug}/scrims/{MONDAY}/8PM/register")
    assert res.status_code == 400 and "suspended" in res.data["detail"]
    page = client_for(manager).get(f"/api/v1/teams/{teams[0].slug}/scrims").data
    assert page["suspended"]["reason"] == "No-show"


def test_withdraw_api(clock, teams, manager):
    base = f"/api/v1/teams/{teams[0].slug}/scrims/{MONDAY}/8PM"
    client_for(manager).post(f"{base}/register")
    res = client_for(manager).post(f"{base}/withdraw")
    assert res.status_code == 200 and res.data["sessions"][0]["mine"] is None


def test_public_lobby(clock, teams, manager, settings):
    settings.PUBLIC_SITE = True
    for t in teams[:13]:
        sv.register(eight(), t, manager)
    data = client_for().get("/api/v1/scrims/tonight").data
    assert data["date"] == MONDAY
    first = data["sessions"][0]
    assert first["session"] == "8PM" and len(first["playing"]) == 12
    assert len(first["waitlist"]) == 1 and "registered_by" not in first["playing"][0]


def test_staff_endpoints(clock, teams, manager, staff):
    assert client_for(manager).get("/api/v1/admin/scrims/night").status_code == 403
    c = client_for(staff)
    res = c.post(f"/api/v1/admin/scrims/{MONDAY}/8PM/add", {"team": teams[5].pk, "note": "sub"})
    assert res.status_code == 200 and res.data["playing"][0]["registered_by"] == "staff@tdl.test"
    res = c.post(f"/api/v1/admin/scrims/{MONDAY}/8PM/remove", {"team": teams[5].pk})
    assert res.status_code == 200 and res.data["playing"] == []
    res = c.patch(f"/api/v1/admin/scrims/{MONDAY}/8PM", {"max_teams": 10}, format="json")
    assert res.data["max_teams"] == 10
    res = c.post(f"/api/v1/admin/scrims/teams/{teams[1].slug}/suspend", {"reason": "rules"})
    assert res.data["suspended"]["reason"] == "rules"
    listed = {t["slug"]: t["suspended"] for t in c.get("/api/v1/admin/scrims/teams").data}
    assert listed[teams[1].slug] and listed[teams[2].slug] is None
    res = c.post(f"/api/v1/admin/scrims/teams/{teams[1].slug}/unsuspend")
    assert res.data["suspended"] is None
    night = c.get(f"/api/v1/admin/scrims/night?date={MONDAY}").data
    assert night["scrim_night"] and [s["session"] for s in night["sessions"]] == ["8PM", "10PM"]
    log = c.get(f"/api/v1/admin/scrims/log?date={MONDAY}").data
    assert [r["action"] for r in log] == [A.STAFF_REMOVED, A.STAFF_ADDED]


def test_settings_api(clock, staff):
    c = client_for(staff)
    res = c.get("/api/v1/admin/scrims/settings").data
    assert res["weekdays"] == [0, 1, 3, 4] and res["closes_at"] == {"8PM": "18:00", "10PM": "20:00"}
    assert res["opens_at"] == "12:01:00" and res["max_teams"] == 12
    bad = c.patch(
        "/api/v1/admin/scrims/settings",
        {"closes_at": {"8PM": "20:30", "10PM": "21:00"}},
        format="json",
    )
    assert bad.status_code == 400
    ok = c.patch("/api/v1/admin/scrims/settings", {"weekdays": [0, 1, 3, 4, 5]}, format="json")
    assert ok.status_code == 200 and sv.is_scrim_night(MONDAY + dt.timedelta(days=5))
