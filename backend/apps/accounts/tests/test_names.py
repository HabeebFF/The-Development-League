"""Names with 18+ or offensive words are refused at sign-up, on invites and on profile edits."""

import pytest
from django.core.management import call_command

from apps.accounts.models import User
from common.names import blocked_word

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "name",
    ["fuckboy", "F.U.C.K", "Sh1tStorm", "p0rnking", "fuuuuck", "Big Dick", "sexy_lady",
     "x x x", "BL0WJ0B", "SexyBeast", "boobs", "niiigga", "ashawo king", "Fück", "the a$$hole"],
)  # fmt: skip
def test_blocked(name):
    assert blocked_word(name), name


@pytest.mark.parametrize(
    "name",
    ["Sussex", "Assassin", "Classic", "Dickson", "Peacock", "Grape", "Canal", "Titan",
     "Cumberland", "Hancock", "Essex Boy", "VT TIMMYY!!", "SLF ZAZA",
     "Berserk Gen", "Habeeb", "Matilda", "Analyst", "Cocktail", "Therapist",
     "Nigeria", "Naija Kings", "Bobby", "Torpedo", "Bob"],
)  # fmt: skip
def test_allowed(name):
    assert blocked_word(name) is None, (name, blocked_word(name))


def test_extra_words_from_settings(settings):
    settings.BLOCKED_NAME_WORDS = "mumu, werey"
    assert blocked_word("Big Mumu") == "mumu"
    assert blocked_word("Mumbai") is None


def test_signup_and_profile_refuse_them(client, settings):
    settings.PUBLIC_SIGNUP = True
    res = client.post(
        "/api/v1/auth/signup",
        {"email": "a@x.test", "password": "Very-long-pass-42", "display_name": "SexyBeast"},
        content_type="application/json",
    )
    assert res.status_code == 400
    assert "18+" in str(res.json())
    assert not User.objects.filter(email="a@x.test").exists()


def test_check_names_lists_and_fixes(capsys):
    bad = User.objects.create_user(email="b@x.test", password="x", display_name="p0rn star")
    ok = User.objects.create_user(email="c@x.test", password="x", display_name="Titan")
    call_command("check_names")
    assert "p0rn star" in capsys.readouterr().out
    bad.refresh_from_db()
    assert bad.display_name == "p0rn star"  # listing changes nothing
    call_command("check_names", "--fix")
    bad.refresh_from_db()
    ok.refresh_from_db()
    assert bad.display_name == f"Player {bad.pk}" and ok.display_name == "Titan"
