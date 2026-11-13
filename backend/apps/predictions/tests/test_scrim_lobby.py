"""Predictions use the teams signed up on Staff > Scrims, once sign-up closes."""

import datetime as dt

import pytest

from apps.predictions import auto
from apps.predictions.models import Fixture, Market
from apps.scrims import services as scrims

from .test_auto import lg as _lg  # noqa: F401  (the "lg" fixture)
from .test_auto import made, next_weekday
from .test_player_rules import bet
from .test_settlement import make_user

pytestmark = pytest.mark.django_db
C, S = Market.Category, Market.Status


@pytest.fixture
def lg(_lg):  # noqa: F811  (uses the imported fixture)
    """The league from ``test_auto``: last week's 8PM and 10PM sessions, plus "Idle"."""
    return _lg


@pytest.fixture(autouse=True)
def _on(settings):
    settings.PREDICTIONS_ENABLED = True


@pytest.fixture
def night(monkeypatch):
    """A Monday at least two days ahead, with a settable Lagos clock for sign-up."""
    date = next_weekday(0)

    def at(hour, minute=0):
        moment = dt.datetime.combine(date, dt.time(hour, minute), tzinfo=scrims.local_tz())
        monkeypatch.setattr(scrims, "now", lambda: moment)

    at(13)
    return date, at


@pytest.fixture
def staff():
    from apps.accounts.models import StaffProfile

    user = make_user("staff@tdl.test")
    StaffProfile.objects.create(user=user)
    return user


def sign_up(date, session, teams, staff):
    scrim = scrims.get_session(date, session)
    for t in teams:
        scrims.staff_add(scrim, t, staff)
    return scrim


def booyah_teams(date, session, match=2):
    m = made(date, session).get(title=f"Booyah · Match {match}")
    return sorted(m.outcomes.filter(is_active=True).values_list("team__name", flat=True))


def test_markets_wait_for_sign_up_to_close(lg, night, staff):
    date, at = night
    sign_up(date, "8PM", [lg["teams"][n] for n in ("Alpha", "Golf", "Idle")], staff)
    report = auto.run(date, force=True)
    assert "8PM: waiting for sign-up to close at 6:00pm." in report["notes"]
    assert "10PM: waiting for sign-up to close at 8:00pm." in report["notes"]
    assert not made(date, "8PM").exists()


def test_lobby_is_the_teams_signed_up_not_last_session(lg, night, staff):
    date, at = night
    sign_up(date, "8PM", [lg["teams"][n] for n in ("Alpha", "Golf", "Idle")], staff)
    at(18, 1)
    report = auto.run(date, force=True)
    whole = Fixture.objects.get(date=date, session="8PM", match_number=None)
    assert sorted(whole.teams.values_list("name", flat=True)) == ["Alpha", "Golf", "Idle"]
    assert booyah_teams(date, "8PM") == ["Alpha", "Golf", "Idle"]
    # 10PM sign-up is still open.
    assert "10PM: waiting for sign-up to close at 8:00pm." in report["notes"]
    assert not made(date, "10PM").exists()


def test_fewer_than_two_signed_up_means_no_markets(lg, night, staff):
    date, at = night
    sign_up(date, "8PM", [lg["teams"]["Alpha"]], staff)
    at(18, 1)
    report = auto.run(date, force=True)
    assert any("fewer than 2 teams signed up" in n for n in report["notes"])
    assert not made(date, "8PM").exists()


def test_staff_changes_after_close_remake_markets(
    lg, night, staff, django_capture_on_commit_callbacks
):
    date, at = night
    t = lg["teams"]
    scrim = sign_up(date, "8PM", [t["Alpha"], t["Bravo"], t["Golf"]], staff)
    at(18, 1)
    auto.run(date, force=True)
    taken = made(date, "8PM").get(title="Booyah · Match 1")
    bet(make_user("fan@tdl.test"), taken)
    own = made(date, "8PM").get(title="Golf top 3 · Match 1")
    bet(make_user("fan2@tdl.test"), own)
    with django_capture_on_commit_callbacks(execute=True):
        scrims.staff_remove(scrim, t["Golf"], staff)
        scrims.staff_add(scrim, t["Idle"], staff)
    whole = Fixture.objects.get(date=date, session="8PM", match_number=None)
    assert sorted(whole.teams.values_list("name", flat=True)) == ["Alpha", "Bravo", "Idle"]
    # Markets nobody predicted on follow the new lobby.
    assert booyah_teams(date, "8PM") == ["Alpha", "Bravo", "Idle"]
    # The market with a prediction keeps its choices, but Golf is switched off for new ones.
    taken.refresh_from_db()
    assert taken.outcomes.get(team__name="Golf").is_active is False
    assert taken.outcomes.get(team__name="Alpha").is_active is True
    # A market about Golf alone with predictions on it is suspended.
    own.refresh_from_db()
    assert own.status == S.SUSPENDED


def test_changes_before_close_make_nothing_yet(
    lg, night, staff, django_capture_on_commit_callbacks
):
    date, at = night
    with django_capture_on_commit_callbacks(execute=True):
        sign_up(date, "8PM", [lg["teams"][n] for n in ("Alpha", "Bravo")], staff)
    assert not made(date).exists()
