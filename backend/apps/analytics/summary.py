"""The staff analytics page: totals, a daily chart and top lists for a date range."""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Count, Min
from django.db.models.functions import ExtractHour, TruncDate
from django.utils import timezone

from .models import PageView

RANGES = {"today": 1, "7d": 7, "30d": 30, "90d": 90, "all": None}
ONLINE_MINUTES = 5
TOP = 10

PAGES = {
    "/": "Home",
    "/standings": "Standings",
    "/results": "Results",
    "/teams": "Teams",
    "/cards": "Player cards",
    "/awards": "Awards",
    "/kills": "Kill list",
    "/ratings": "Player ratings",
    "/team": "Team home",
    "/team/coach": "Team coach",
    "/team/members": "Team members",
    "/staff": "Staff home",
    "/auth/login": "Sign in",
}


def page_name(path: str) -> str:
    """A readable name for a page: "Standings", "OUTPOST-33", "Day 13 / Match 2 replay"."""
    from apps.league.models import Match, MatchDay, Player, Team

    if path in PAGES:
        return PAGES[path]
    try:
        if m := re.fullmatch(r"/teams/([\w-]+)", path):
            return Team.objects.get(slug=m[1]).name
        if m := re.fullmatch(r"/results/(\d+)", path):
            return str(MatchDay.objects.get(pk=m[1]))
        if m := re.fullmatch(r"(?:/team|/staff)?/matches/(\d+)(?:/(replay|rotations|plot))?", path):
            match = Match.objects.select_related("match_day").get(pk=m[1])
            return f"{match} {m[2]}" if m[2] else str(match)
        if m := re.fullmatch(r"/cards/(\d+)", path):
            return f"{Player.objects.get(pk=m[1]).display_name} card"
    except (Team.DoesNotExist, MatchDay.DoesNotExist, Match.DoesNotExist, Player.DoesNotExist):
        return path
    if path.startswith("/invite/"):
        return "Team invite"
    if path.startswith("/staff/"):
        return "Staff: " + path.removeprefix("/staff/").split("/")[0].replace("-", " ")
    return path


def _counts(rows, field: str, empty: str = "") -> list[dict]:
    out = rows.values(field).annotate(views=Count("id"), visitors=Count("visitor", distinct=True))
    return [
        {"name": row[field] or empty, "views": row["views"], "visitors": row["visitors"]}
        for row in out.order_by("-views", field)[:TOP]
    ]


def summary(range_key: str, now: datetime | None = None) -> dict:
    """Days and hours are in the league's time zone (``ANALYTICS_TIME_ZONE``)."""
    with timezone.override(ZoneInfo(settings.ANALYTICS_TIME_ZONE)):
        return _summary(range_key, now or timezone.now())


def _summary(range_key: str, now: datetime) -> dict:
    today = timezone.localdate(now)
    visits = PageView.objects.exclude(audience=PageView.Audience.STAFF)
    days = RANGES[range_key]
    if days is None:
        first = PageView.objects.aggregate(first=Min("created_at"))["first"]
        start_day = timezone.localdate(first) if first else today
    else:
        start_day = today - timedelta(days=days - 1)
    start = timezone.make_aware(datetime.combine(start_day, time.min))
    rows = visits.filter(created_at__gte=start, created_at__lte=now)

    views = rows.count()
    # Each day's codes are new, so this adds up each day's unique visitors.
    visitors = rows.values("visitor").distinct().count()

    per_day = {
        row["day"]: row
        for row in rows.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(views=Count("id"), visitors=Count("visitor", distinct=True))
    }
    by_day = []
    day = start_day
    while day <= today:
        row = per_day.get(day, {})
        by_day.append(
            {
                "date": day.isoformat(),
                "views": row.get("views", 0),
                "visitors": row.get("visitors", 0),
            }
        )
        day += timedelta(days=1)

    hours = dict(
        rows.annotate(hour=ExtractHour("created_at"))
        .values("hour")
        .annotate(views=Count("id"))
        .values_list("hour", "views")
    )

    pages = _counts(rows, "path")
    for page in pages:
        page["path"] = page["name"]
        page["name"] = page_name(page["path"])

    online = visits.filter(created_at__gte=now - timedelta(minutes=ONLINE_MINUTES))
    return {
        "range": range_key,
        "start": start_day.isoformat(),
        "end": today.isoformat(),
        "totals": {
            "views": views,
            "visitors": visitors,
            "pages_per_visitor": round(views / visitors, 1) if visitors else 0,
            "online_now": online.values("visitor").distinct().count(),
            "staff_views": PageView.objects.filter(
                audience=PageView.Audience.STAFF, created_at__gte=start, created_at__lte=now
            ).count(),
        },
        "by_day": by_day,
        "hours": [{"hour": h, "views": hours.get(h, 0)} for h in range(24)],
        "pages": pages,
        "sources": _counts(rows, "source", "Direct"),
        "devices": _counts(rows, "device"),
        "browsers": _counts(rows, "browser"),
        "systems": _counts(rows, "os"),
        "audience": _counts(rows, "audience"),
    }
