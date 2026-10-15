"""Visitor analytics: what gets counted, how visitors are told apart, and the staff summary."""

from datetime import timedelta
from unittest import mock

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Membership, User
from apps.analytics import tracking
from apps.analytics.models import PageView
from apps.analytics.summary import page_name, summary
from apps.analytics.tasks import purge_old_views_task
from apps.league.models import Match, MatchDay, ScoringRule, Season, Stage, Team

PHONE = (
    "Mozilla/5.0 (Linux; Android 13; SM-A145F) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Mobile Safari/537.36"
)
IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)
DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0"
)
TABLET = (
    "Mozilla/5.0 (Linux; Android 12; SM-X200) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36"
)


@pytest.fixture(autouse=True)
def _clear_throttle():
    cache.clear()


def hit(client=None, path="/", ua=PHONE, ip="1.2.3.4", **extra):
    client = client or APIClient()
    return client.post(
        "/api/v1/analytics/hit",
        {"path": path, **extra},
        format="json",
        HTTP_USER_AGENT=ua,
        HTTP_X_FORWARDED_FOR=f"{ip}, 10.0.0.1",
    )


def staff_client():
    client = APIClient()
    client.force_authenticate(User.objects.create_user(email="staff@tdl.test", is_staff=True))
    return client


# -- Parsing -----------------------------------------------------------------------------


def test_devices_browsers_and_systems():
    assert [tracking.device(ua) for ua in (PHONE, IPHONE, DESKTOP, TABLET)] == [
        "phone", "phone", "desktop", "tablet"
    ]  # fmt: skip
    assert [tracking.browser(ua) for ua in (PHONE, IPHONE, DESKTOP)] == ["Chrome", "Safari", "Edge"]
    assert [tracking.operating_system(ua) for ua in (PHONE, IPHONE, DESKTOP)] == [
        "Android", "iOS", "Windows"
    ]  # fmt: skip


def test_bots_and_link_previews_are_not_people():
    for ua in ("", "WhatsApp/2.23.20.0", "Discordbot/2.0", "Googlebot/2.1", "curl/8.4.0",
               "facebookexternalhit/1.1", "Mozilla/5.0 HeadlessChrome/120"):  # fmt: skip
        assert tracking.is_bot(ua), ua
    assert not tracking.is_bot(PHONE)


@pytest.mark.parametrize(
    ("referrer", "ref", "expected"),
    [
        ("", "", ""),
        ("https://www.google.com.ng/", "", "Google"),
        ("https://l.facebook.com/l.php?u=x", "", "Facebook"),
        ("https://t.co/abc", "", "X"),
        ("https://discord.com/channels/1/2", "", "Discord"),
        ("android-app://com.whatsapp/", "", "WhatsApp"),
        ("https://site.test/standings", "", ""),
        ("https://someblog.example.com/post", "", "someblog.example.com"),
        ("", "wa", "WhatsApp"),
        ("https://t.co/abc", "discord", "Discord"),
        ("", "flyer<script>", "Flyerscript"),
    ],
)
def test_sources(referrer, ref, expected):
    assert tracking.source(referrer, ref, "site.test") == expected


def test_paths_are_cleaned():
    assert tracking.clean_path("/teams/alpha/?x=1#top") == "/teams/alpha"
    assert tracking.clean_path("/") == "/"
    for bad in ("", "teams", "//evil.com", "https://x.com/", "/api/v1/me"):
        assert tracking.clean_path(bad) is None


def test_visitor_code_is_the_same_all_day_and_new_the_next():
    day = timezone.localdate()
    code = tracking.visitor_code("1.2.3.4", PHONE, day)
    assert code == tracking.visitor_code("1.2.3.4", PHONE, day)
    assert code != tracking.visitor_code("1.2.3.5", PHONE, day)
    assert code != tracking.visitor_code("1.2.3.4", PHONE, day + timedelta(days=1))
    assert "1.2.3.4" not in code and len(code) == 16


# -- Recording ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_visit_is_stored_without_the_ip():
    assert hit(path="/standings?ref=wa", ref="wa").status_code == 201
    view = PageView.objects.get()
    assert (view.path, view.source, view.device, view.browser, view.os, view.audience) == (
        "/standings", "WhatsApp", "phone", "Chrome", "Android", "guest"
    )  # fmt: skip
    assert "1.2.3.4" not in str(view.__dict__)


@pytest.mark.django_db
def test_bots_and_bad_paths_are_ignored_quietly():
    assert hit(ua="Discordbot/2.0").status_code == 204
    assert hit(path="https://evil.example/").status_code == 204
    assert APIClient().post("/api/v1/analytics/hit", "nonsense", content_type="application/json",
                            HTTP_USER_AGENT=PHONE).status_code in (204, 400)  # fmt: skip
    assert not PageView.objects.exists()


@pytest.mark.django_db
def test_signed_in_visits_are_marked_member_or_staff():
    team = Team.objects.create(name="Alpha", slug="alpha")
    member = User.objects.create_user(email="m@tdl.test")
    Membership.objects.create(user=member, team=team)
    client = APIClient()
    client.force_authenticate(member)
    hit(client)
    hit(staff_client())
    assert sorted(PageView.objects.values_list("audience", flat=True)) == ["member", "staff"]


@pytest.mark.django_db
def test_hits_are_rate_limited():
    with mock.patch("rest_framework.throttling.ScopedRateThrottle.THROTTLE_RATES",
                    {"analytics_hit": "2/min"}):  # fmt: skip
        codes = [hit().status_code for _ in range(3)]
    assert codes == [201, 201, 429]


# -- Summary -----------------------------------------------------------------------------


def _view(path="/", visitor="a", ago=timedelta(0), **fields):
    view = PageView.objects.create(path=path, visitor=visitor, device="phone", browser="Chrome",
                                   os="Android", **fields)  # fmt: skip
    PageView.objects.filter(pk=view.pk).update(created_at=timezone.now() - ago)
    return view


@pytest.mark.django_db
def test_summary_counts_people_not_staff():
    _view("/", "a")
    _view("/standings", "a", source="WhatsApp")
    _view("/standings", "b", ago=timedelta(days=2))
    _view("/standings", "old", ago=timedelta(days=40))
    _view("/staff", "s", audience="staff")
    data = summary("7d")
    assert data["totals"] == {"views": 3, "visitors": 2, "pages_per_visitor": 1.5,
                              "online_now": 1, "staff_views": 1, "actions": 0, "visits": 2,
                              "avg_visit_s": 0, "bounce_rate": 50}  # fmt: skip
    assert len(data["by_day"]) == 7 and data["by_day"][-1]["views"] == 2
    assert sum(d["visitors"] for d in data["by_day"]) == 2
    assert data["pages"][0] == {"name": "Standings", "path": "/standings", "views": 2,
                                "visitors": 2, "avg_s": 0}  # fmt: skip
    assert {s["name"]: s["views"] for s in data["sources"]} == {"Direct": 2, "WhatsApp": 1}
    assert sum(h["views"] for h in data["hours"]) == 3 and len(data["hours"]) == 24
    assert summary("today")["totals"]["views"] == 2
    assert summary("all")["totals"]["views"] == 4
    assert len(summary("all")["by_day"]) == 41


@pytest.mark.django_db
def test_summary_is_staff_only():
    assert APIClient().get("/api/v1/analytics/summary").status_code in (401, 403)
    member = APIClient()
    member.force_authenticate(User.objects.create_user(email="m@tdl.test"))
    assert member.get("/api/v1/analytics/summary").status_code == 403
    staff = staff_client()
    assert staff.get("/api/v1/analytics/summary?range=30d").json()["range"] == "30d"
    assert staff.get("/api/v1/analytics/summary?range=year").status_code == 400


@pytest.mark.django_db
def test_page_names():
    team = Team.objects.create(name="OUTPOST-33", slug="outpost-33")
    season = Season.objects.create(name="S1", scoring_rule=ScoringRule.objects.first())
    day = MatchDay.objects.create(stage=Stage.objects.create(season=season, name="L"), number=13,
                                  title="Day 13 8PM")  # fmt: skip
    match = Match.objects.create(match_day=day, number=2)
    assert page_name("/") == "Home"
    assert page_name(f"/teams/{team.slug}") == "OUTPOST-33"
    assert page_name(f"/results/{day.pk}") == "Day 13 8PM"
    assert page_name(f"/matches/{match.pk}/replay") == "Day 13 8PM / Match 2 replay"
    assert page_name("/teams/nobody") == "/teams/nobody"
    assert page_name("/staff/upload") == "Staff: upload"


@pytest.mark.django_db
def test_old_views_are_purged():
    _view(visitor="old", ago=timedelta(days=401))
    _view(visitor="new", ago=timedelta(days=30))
    assert purge_old_views_task() == 1
    assert list(PageView.objects.values_list("visitor", flat=True)) == ["new"]


@pytest.mark.django_db
def test_hours_and_days_are_in_lagos_time():
    now = timezone.now().replace(hour=23, minute=30)  # 00:30 the next day in Lagos
    view = _view("/", "a")
    PageView.objects.filter(pk=view.pk).update(created_at=now)
    data = summary("today", now=now)
    assert data["end"] == (now + timedelta(hours=1)).date().isoformat()
    assert [h["hour"] for h in data["hours"] if h["views"]] == [0]
