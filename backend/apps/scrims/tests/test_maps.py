"""Each match's map is drawn when a night's sign-up opens (Habeeb, 2026-11-20): shown to
everyone, and staff can draw again or set them until the session starts."""

import datetime as dt
import random
from collections import Counter

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import StaffProfile
from apps.maps.models import Map
from apps.predictions.models import AutoSettings
from apps.scrims import maps as mp
from apps.scrims import services as sv
from apps.scrims.models import ScrimSession, ScrimSettings

pytestmark = pytest.mark.django_db

MONDAY = dt.date(2026, 11, 16)
SUNDAY = dt.date(2026, 11, 15)


@pytest.fixture(autouse=True)
def rules():
    ScrimSettings.objects.update_or_create(
        pk=1,
        defaults={"opens_at": dt.time(20), "opens_days_before": 1, "weekdays": [0, 1, 3, 4]},
    )


@pytest.fixture
def clock(monkeypatch):
    def set_to(date, hour, minute=0):
        moment = dt.datetime.combine(date, dt.time(hour, minute), tzinfo=sv.local_tz())
        monkeypatch.setattr(sv, "now", lambda: moment)
        monkeypatch.setattr(sv, "today", lambda: date)

    set_to(SUNDAY, 21)  # Monday's sign-up opened at 8pm on Sunday
    return set_to


@pytest.fixture
def staff():
    user = get_user_model().objects.create_user(email="staff@tdl.test", password="pw-123456")
    StaffProfile.objects.create(user=user)
    return user


def five():
    return set(Map.objects.filter(is_active=True).values_list("pk", flat=True))


def test_the_five_seeded_maps_can_be_drawn():
    assert len(five()) == 5


@pytest.mark.parametrize("seed", range(20))
def test_five_matches_play_every_map_once(seed):
    maps = sorted(five())
    order = mp.draw(5, maps, random.Random(seed))
    assert sorted(order) == maps


@pytest.mark.parametrize("seed", range(20))
def test_a_longer_night_repeats_a_map_but_never_back_to_back(seed):
    maps = sorted(five())
    order = mp.draw(7, maps, random.Random(seed))
    assert len(order) == 7
    assert set(order[:5]) == set(maps)
    assert all(a != b for a, b in zip(order, order[1:], strict=False))


def test_the_order_changes_from_night_to_night():
    maps = sorted(five())
    orders = {tuple(mp.draw(5, maps, random.Random(seed))) for seed in range(30)}
    assert len(orders) > 10


def test_drawing_more_keeps_the_maps_already_drawn():
    maps = sorted(five())
    first = mp.draw(5, maps, random.Random(1))
    assert mp.draw(6, maps, random.Random(2), start=first)[:5] == first


def test_no_maps_before_sign_up_opens(clock):
    clock(SUNDAY, 19, 59)
    scrim = sv.get_session(MONDAY, "8PM")
    assert mp.ensure(scrim) == []
    assert ScrimSession.objects.get(pk=scrim.pk).maps == []


def test_maps_are_drawn_once_when_sign_up_opens(clock):
    scrim = sv.get_session(MONDAY, "8PM")
    drawn = mp.ensure(scrim)
    assert set(drawn) == five()
    scrim.refresh_from_db()
    assert scrim.maps == drawn and scrim.maps_drawn_at is not None
    assert mp.ensure(scrim) == drawn  # never drawn again by itself
    assert mp.map_for(MONDAY, "8PM", 3) == drawn[2]
    assert mp.map_for(MONDAY, "8PM", 9) is None


def test_the_sweep_draws_both_sessions(clock):
    assert mp.draw_due() == 2
    assert mp.draw_due() == 0
    for session in ("8PM", "10PM"):
        assert set(ScrimSession.objects.get(date=MONDAY, session=session).maps) == five()


def test_a_six_map_night_gets_a_sixth(clock):
    scrim = sv.get_session(MONDAY, "10PM")
    first = mp.ensure(scrim)
    conf = AutoSettings.get()
    conf.long_sessions = {f"{MONDAY.isoformat()} 10PM": 6}
    conf.save()
    longer = mp.ensure(ScrimSession.objects.get(pk=scrim.pk))
    assert longer[:5] == first and len(longer) == 6 and longer[5] != longer[4]


def test_the_public_lobby_shows_the_maps(clock):
    data = APIClient().get("/api/v1/scrims/tonight").json()
    monday = next(n for n in data["nights"] if n["date"] == MONDAY.isoformat())
    for session in monday["sessions"]:
        assert [m["id"] for m in session["maps"]] == ScrimSession.objects.get(
            date=MONDAY, session=session["session"]
        ).maps
        assert {m["name"] for m in session["maps"]} == set(
            Map.objects.values_list("name", flat=True)
        )


def test_staff_set_the_maps_by_hand(clock, staff):
    client = APIClient()
    client.force_authenticate(staff)
    url = f"/api/v1/admin/scrims/{MONDAY.isoformat()}/8PM/maps"
    pool = client.get(url).json()
    assert pool["matches"] == 5 and len(pool["pool"]) == 5
    kalahari = Map.objects.get(name="Kalahari").pk
    bermuda = Map.objects.get(name="Bermuda").pk
    chosen = [kalahari, bermuda, kalahari, bermuda, kalahari]
    r = client.post(url, {"maps": chosen}, format="json")
    assert r.status_code == 200, r.content
    assert [m["id"] for m in r.json()["maps"]] == chosen
    scrim = ScrimSession.objects.get(date=MONDAY, session="8PM")
    assert scrim.maps == chosen and scrim.maps_set_by == staff
    # Wrong number, unknown map.
    r = client.post(url, {"maps": chosen[:4]}, format="json")
    assert r.status_code == 400 and "pick 5 maps" in r.json()["detail"]
    r = client.post(url, {"maps": [*chosen[:4], 99999]}, format="json")
    assert r.status_code == 400 and "Unknown map" in r.json()["detail"]


def test_staff_draw_again(clock, staff):
    scrim = sv.get_session(MONDAY, "8PM")
    before = mp.ensure(scrim)
    seen = Counter()
    for seed in range(5):
        seen[tuple(mp.redraw(scrim, staff, random.Random(seed)))] += 1
    assert len(seen) > 1
    scrim.refresh_from_db()
    assert set(scrim.maps) == set(before) and scrim.maps_set_by == staff


def test_maps_are_fixed_once_the_session_starts(clock, staff):
    scrim = sv.get_session(MONDAY, "8PM")
    mp.ensure(scrim)
    clock(MONDAY, 20, 0)
    with pytest.raises(sv.ScrimError, match="started"):
        mp.redraw(scrim, staff)


def test_only_staff_change_maps(clock):
    user = get_user_model().objects.create_user(email="fan@tdl.test", password="pw-123456")
    client = APIClient()
    client.force_authenticate(user)
    r = client.post(f"/api/v1/admin/scrims/{MONDAY.isoformat()}/8PM/maps", {"redraw": True})
    assert r.status_code == 403
