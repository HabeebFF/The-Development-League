"""In-depth analytics: time on page, actions, visits, each day, each person."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Membership, User
from apps.analytics import detail
from apps.analytics.models import Action, PageView
from apps.analytics.summary import summary
from apps.analytics.tests.test_analytics import PHONE, hit, staff_client
from apps.analytics.tracking import api_action_name
from apps.league.models import Team


@pytest.fixture(autouse=True)
def _clear_throttle():
    cache.clear()


def post(url, data):
    return APIClient().post(f"/api/v1/analytics/{url}", data, format="json")


def lagos_noon():
    """Noon today in Lagos, so test views never cross midnight."""
    now = timezone.now().astimezone(detail.league_tz())
    return now.replace(hour=12, minute=0, second=0, microsecond=0)


def view(path="/", visitor="aaaa1111", at=None, user=None, seconds=None, audience="guest"):
    v = PageView.objects.create(path=path, visitor=visitor, device="phone", browser="Chrome",
                                os="Android", user=user, duration_s=seconds,
                                audience=audience)  # fmt: skip
    PageView.objects.filter(pk=v.pk).update(created_at=at or lagos_noon())
    v.refresh_from_db()
    return v


@pytest.mark.django_db
def test_time_and_actions_are_reported_by_key_without_signing_in():
    key = hit(path="/matches/3/replay").json()["key"]
    assert post("time", {"key": key, "seconds": 40}).status_code == 204
    assert post("time", {"key": key, "seconds": 25}).status_code == 204  # late ping: keep 40
    assert post("time", {"key": key, "seconds": 99999}).status_code == 204  # capped at 1 hour
    post("action", {"key": key, "name": "  Pressed   Play ", "detail": "Day 13 match 2"})
    post("action", {"key": key, "api": {"method": "POST", "path": "/auth/login", "ok": False}})
    post("action", {"key": key, "api": {"method": "POST", "path": "/auth/refresh", "ok": True}})
    post("action", {"key": key, "name": ""})
    post("action", {"key": "not-a-key", "name": "Pressed Play"})
    v = PageView.objects.get()
    assert v.duration_s == 3600
    assert list(v.actions.values_list("name", "detail")) == [
        ("Pressed Play", "Day 13 match 2"), ("Sign-in failed", "/auth/login")
    ]  # fmt: skip


@pytest.mark.django_db
def test_old_keys_cannot_be_reported_on():
    v = view(at=timezone.now() - timedelta(days=2))
    post("time", {"key": str(v.key), "seconds": 10})
    post("action", {"key": str(v.key), "name": "Pressed Play"})
    v.refresh_from_db()
    assert v.duration_s is None and not Action.objects.exists()


@pytest.mark.django_db
def test_signed_in_views_are_linked_to_the_account():
    user = User.objects.create_user(email="p@tdl.test", display_name="VT.HABEEB")
    client = APIClient()
    client.force_authenticate(user)
    hit(client, path="/standings")
    assert PageView.objects.get().user == user


def act(v, name, detail=""):
    a = Action.objects.create(view=v, name=name, detail=detail)
    Action.objects.filter(pk=a.pk).update(created_at=v.created_at)
    return a


def test_api_action_names():
    assert api_action_name("POST", "/auth/login", True) == "Signed in"
    assert api_action_name("POST", "/auth/logout", True) == "Signed out"
    assert api_action_name("POST", "/invites/abc", True) == "Accepted an invite"
    assert api_action_name("PATCH", "/admin/teams/alpha", True) == "Edited a team"
    assert (
        api_action_name("POST", "/uploads/batches/4/files", False) == "Saved match files (failed)"
    )
    assert api_action_name("DELETE", "/admin/whatever/1", True) == "Deleted whatever"
    assert api_action_name("GET", "/teams", True) is None
    assert api_action_name("POST", "/analytics/hit", True) is None


def test_visits_split_after_30_quiet_minutes():
    noon = lagos_noon()
    views = [PageView(created_at=noon, duration_s=600),
             PageView(created_at=noon + timedelta(minutes=35), duration_s=None),  # 25 min after
             PageView(created_at=noon + timedelta(minutes=80))]  # fmt: skip
    assert [len(v) for v in detail.visits(views)] == [2, 1]


@pytest.mark.django_db
def test_a_day_lists_everyone_and_their_timeline():
    team = Team.objects.create(name="Vortex", slug="vortex")
    user = User.objects.create_user(email="p@tdl.test", display_name="VT.HABEEB")
    Membership.objects.create(user=user, team=team)
    noon = lagos_noon()
    a = view("/standings", "aaaa1111", noon, user=user, seconds=80, audience="member")
    view("/matches/3/replay", "aaaa1111", noon + timedelta(minutes=2), user=user, seconds=300,
         audience="member")  # fmt: skip
    act(a, "Picked an option", "Week")
    view("/", "bbbb2222", noon + timedelta(hours=1))
    view("/staff", "cccc3333", noon, audience="staff")

    data = detail.day(noon.date())
    assert data["totals"]["people"] == 2 and data["totals"]["signed_in"] == 1
    assert data["totals"]["actions"] == 1 and data["totals"]["seconds"] == 380
    assert data["totals"]["visits"] == 2 and data["totals"]["bounce_rate"] == 50
    people = {p["key"]: p for p in data["people"]}
    me = people[f"u{user.pk}"]
    assert (me["name"], me["team"], me["pages"], me["actions"], me["visits"]) == (
        "VT.HABEEB", "Vortex", 2, 1, 1
    )  # fmt: skip
    assert people["vbbbb2222"]["name"] == "Visitor BBBB"
    assert data["hours"][12] == {"hour": 12, "views": 2, "actions": 1}
    assert detail.day(noon.date(), "staff")["totals"]["people"] == 1
    assert detail.day(noon.date(), "guests")["totals"]["people"] == 1

    line = detail.timeline(f"u{user.pk}", noon.date())
    pages = line["visits"][0]["pages"]
    assert [p["name"] for p in pages] == ["Standings", "/matches/3/replay"]
    assert pages[0]["actions"][0]["name"] == "Picked an option"
    assert detail.timeline("vbbbb2222", noon.date())["person"]["name"] == "Visitor BBBB"
    assert detail.timeline("vnobody", noon.date()) is None
    assert detail.timeline("x1", noon.date()) is None


@pytest.mark.django_db
def test_people_and_actions_reports():
    user = User.objects.create_user(email="p@tdl.test")
    noon = timezone.now() - timedelta(minutes=5)
    a = view("/cards", "aaaa1111", noon, user=user, seconds=30)
    view("/cards", "aaaa9999", noon - timedelta(days=1), user=user)
    act(a, "Pressed Download", "Card")
    act(a, "Pressed Download", "Card")
    b = view("/kills", "bbbb2222", noon)
    act(b, "Picked an option", "Month")

    people = detail.people(30)["people"]
    assert len(people) == 1
    assert (people[0]["name"], people[0]["pages"], people[0]["actions"], people[0]["days_active"],
            people[0]["new"]) == ("p@tdl.test", 2, 2, 2, True)  # fmt: skip

    end = timezone.now()
    report = detail.actions_report(end - timedelta(days=7), end, "everyone")
    assert report["total"] == 3
    assert report["actions"][0] == {"name": "Pressed Download", "times": 2, "people": 1,
                                    "details": [{"detail": "Card", "times": 2}]}  # fmt: skip
    assert detail.actions_report(end - timedelta(days=7), end, "everyone", "/kills")["total"] == 1
    assert summary("7d")["actions"][0]["name"] == "Pressed Download"
    assert summary("7d", who="signed_in")["totals"]["views"] == 2


@pytest.mark.django_db
def test_detail_pages_are_staff_only():
    for url in ("day", "timeline?person=u1", "people", "actions"):
        assert APIClient().get(f"/api/v1/analytics/{url}").status_code in (401, 403)
    staff = staff_client()
    assert staff.get("/api/v1/analytics/day?date=2026-10-12&who=guests").status_code == 200
    assert staff.get("/api/v1/analytics/day?date=nope").status_code == 400
    assert staff.get("/api/v1/analytics/day?who=robots").status_code == 400
    assert staff.get("/api/v1/analytics/timeline?person=u999").status_code == 404
    assert staff.get("/api/v1/analytics/people?days=7").json()["days"] == 7
    assert staff.get("/api/v1/analytics/actions?range=30d&path=/kills").json()["path"] == "/kills"
    assert PHONE  # shared user agent used by hit()
