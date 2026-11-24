"""Calling scrims off: sign-up fees and predictions go back, and nothing reopens by itself."""
# ruff: noqa: F811 (pytest fixtures imported from the other scrim and prediction tests)

from io import StringIO

import pytest
from django.core.management import call_command

from apps.predictions import auto
from apps.predictions.models import AutoSettings, Fixture, LedgerEntry, Market
from apps.predictions.tests.test_auto import lg, next_weekday  # noqa: F401
from apps.predictions.tests.test_settlement import bet
from apps.scrims import services as sv
from apps.scrims.models import Registration, ScrimLog, ScrimSettings

from .test_day_early import (  # noqa: F401
    THURSDAY,
    WEDNESDAY,
    balance,
    client_for,
    clock,
    fill,
    linked_player,
    players,
    rules,
    staff,
    teams,
    thursday,
)

pytestmark = pytest.mark.django_db
R, A, K = Registration.Status, ScrimLog.Action, LedgerEntry.Kind


def test_calling_off_the_night_refunds_every_fee_and_blocks_sign_up(clock, teams, players, staff):
    fill(teams, players, 12)  # 8PM full and locked
    sv.register(thursday(), teams[12], players[12])  # waitlist, paid
    sv.register(thursday("10PM"), teams[13], players[13])
    sv.staff_invite(thursday("10PM"), teams[0], staff)  # invited: nothing paid
    assert balance(players[0]) == 1000 - 500

    report = sv.call_off(THURSDAY, staff, "Scrims off this week")

    eight, ten = report["sessions"]
    assert (eight["teams"], eight["fees"], eight["dc"]) == (13, 13, 6500)
    assert (ten["teams"], ten["fees"], ten["dc"]) == (2, 1, 500)
    assert all(balance(p) == 1000 for p in players)
    assert not Registration.objects.exists()
    assert ScrimLog.objects.filter(action=A.CALLED_OFF).count() == 15
    assert ScrimLog.objects.filter(action=A.REFUNDED).count() == 14
    scrim = thursday()
    assert scrim.called_off_at and scrim.called_off_by == staff and scrim.locked_at is None
    # A night off for scrims and predictions alike.
    assert THURSDAY.isoformat() in ScrimSettings.get().skip_dates
    assert THURSDAY.isoformat() in AutoSettings.get().skip_dates
    with pytest.raises(sv.ScrimError, match="no scrims|called off"):
        sv.register(thursday(), teams[0], players[0])
    with pytest.raises(sv.ScrimError, match="called off. Scrims off this week"):
        sv.staff_add(thursday(), teams[0], staff)


def test_calling_off_twice_refunds_once(clock, teams, players, staff):
    fill(teams, players, 2)
    sv.call_off(THURSDAY, staff)
    sv.call_off(THURSDAY, staff)
    assert balance(players[0]) == 1000
    assert LedgerEntry.objects.filter(kind=K.SCRIM_REFUND).count() == 2


def test_one_session_can_be_called_off_and_put_back_on(clock, teams, players, staff):
    fill(teams, players, 2)
    sv.register(thursday("10PM"), teams[5], players[5])
    sv.call_off(THURSDAY, staff, sessions=["8PM"])
    assert balance(players[0]) == 1000 and balance(players[5]) == 500
    assert sv.lobby(thursday("10PM")) == [teams[5].pk]
    assert THURSDAY.isoformat() not in ScrimSettings.get().skip_dates
    with pytest.raises(sv.ScrimError, match="called off"):
        sv.register(thursday(), teams[0], players[0])
    assert sv.resume(THURSDAY, staff, ["8PM"]) == ["8PM"]
    assert sv.register(thursday(), teams[0], players[0]).status == R.REGISTERED


def test_resuming_the_night_takes_it_off_the_nights_off(clock, teams, players, staff):
    sv.call_off(THURSDAY, staff)
    sv.resume(THURSDAY, staff)
    assert THURSDAY.isoformat() not in ScrimSettings.get().skip_dates
    assert THURSDAY.isoformat() not in AutoSettings.get().skip_dates
    assert sv.register(thursday(), teams[0], players[0]).status == R.REGISTERED


def test_staff_preview_then_call_off_and_resume(clock, teams, players, staff):
    fill(teams, players, 3)
    api = client_for(staff)
    plan = api.get("/api/v1/admin/scrims/call-off", {"date": THURSDAY.isoformat()}).json()
    assert [s["dc"] for s in plan["sessions"]] == [1500, 0]
    assert balance(players[0]) == 500  # the preview changes nothing

    reply = api.post(
        "/api/v1/admin/scrims/call-off",
        {"date": THURSDAY.isoformat(), "session": "8PM", "reason": "Server down"},
        format="json",
    )
    assert reply.status_code == 200, reply.content
    eight = reply.json()["sessions"][0]
    assert eight["called_off"] and eight["called_off_reason"] == "Server down"
    assert eight["playing"] == []
    assert balance(players[0]) == 1000

    reply = api.post(
        "/api/v1/admin/scrims/call-off/resume",
        {"date": THURSDAY.isoformat(), "session": "8PM"},
        format="json",
    )
    assert reply.status_code == 200 and not reply.json()["sessions"][0]["called_off"]


def test_only_staff_can_call_off(clock, teams, players):
    reply = client_for(players[0]).post(
        "/api/v1/admin/scrims/call-off", {"date": THURSDAY.isoformat()}, format="json"
    )
    assert reply.status_code == 403


def test_the_command_shows_first_and_acts_with_yes(clock, teams, players, staff):
    fill(teams, players, 2)
    out = StringIO()
    call_command("call_off_scrims", THURSDAY.isoformat(), "--by", staff.email, stdout=out)
    assert "2 fees = 1,000 DC back" in out.getvalue() and "Nothing changed" in out.getvalue()
    assert balance(players[0]) == 500
    call_command(
        "call_off_scrims", THURSDAY.isoformat(), "--by", staff.email, "--yes", stdout=StringIO()
    )
    assert balance(players[0]) == 1000 and thursday().called_off_at


def test_calling_off_refunds_predictions_and_no_markets_come_back(lg, staff, settings):
    settings.PREDICTIONS_ENABLED = True
    ScrimSettings.objects.update_or_create(pk=1, defaults={"weekdays": []})
    date = next_weekday(2)
    auto.run(date)
    fan = linked_player(None, "fan@tdl.test")
    market = Market.objects.filter(fixture__date=date, fixture__session="8PM").first()
    bet(fan, market, market.outcomes.first(), stake=200)
    assert balance(fan) == 800

    report = sv.call_off(date, staff, "Called off")

    assert report["sessions"][0]["bets"] == 1 and report["sessions"][0]["voided"] > 0
    assert balance(fan) == 1000
    assert not Market.objects.filter(fixture__date=date).exclude(status=Market.Status.VOID).exists()
    assert not Fixture.objects.filter(date=date, teams__isnull=False).exists()
    assert auto.run(date)["made"] == []


def test_a_called_off_session_gets_no_markets_even_if_made_by_hand(lg, staff, settings):
    settings.PREDICTIONS_ENABLED = True
    ScrimSettings.objects.update_or_create(pk=1, defaults={"weekdays": []})
    date = next_weekday(2)
    sv.call_off(date, staff, sessions=["8PM"])
    job = auto.Run(date, staff)
    job.session("8PM")
    assert job.made == [] and "called off" in job.notes[0]
