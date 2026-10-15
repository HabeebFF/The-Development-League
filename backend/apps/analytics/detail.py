"""Day by day, people and actions: the in-depth staff analytics.

A person is a signed-in account ("u12") or, without an account, that day's anonymous visitor
code ("v3fa9..."). A visit is a run of pages with no more than 30 minutes of nothing between.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Count, Max, Min, Q, QuerySet, Sum
from django.db.models.functions import ExtractHour, TruncDate
from django.utils import timezone

from .models import Action, PageView
from .summary import page_name

VISIT_GAP = timedelta(minutes=30)
WHO = ("everyone", "signed_in", "guests", "staff")
TOP = 15


def league_tz() -> ZoneInfo:
    return ZoneInfo(settings.ANALYTICS_TIME_ZONE)


def who_filter(views: QuerySet, who: str) -> QuerySet:
    """everyone = all but staff; signed_in / guests split that; staff on its own."""
    staff = Q(audience=PageView.Audience.STAFF)
    if who == "staff":
        return views.filter(staff)
    views = views.exclude(staff)
    if who == "signed_in":
        return views.filter(user__isnull=False)
    if who == "guests":
        return views.filter(user__isnull=True)
    return views


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=league_tz())
    return start, start + timedelta(days=1)


def person_key(view: PageView) -> str:
    return f"u{view.user_id}" if view.user_id else f"v{view.visitor}"


def _teams(user_ids) -> dict[int, str]:
    from apps.accounts.models import Membership

    teams: dict[int, str] = {}
    for m in Membership.objects.filter(user_id__in=user_ids, is_active=True).select_related("team"):
        teams.setdefault(m.user_id, m.team.name)
    return teams


def describe(view: PageView, teams: dict[int, str]) -> dict:
    """Who a person is, as the staff page shows them."""
    if view.user_id:
        user = view.user
        return {
            "key": person_key(view),
            "name": str(user),
            "team": teams.get(view.user_id, ""),
            "signed_in": True,
            "staff": view.audience == PageView.Audience.STAFF,
        }
    return {
        "key": person_key(view),
        "name": f"Visitor {view.visitor[:4].upper()}",
        "team": "",
        "signed_in": False,
        "staff": False,
    }


def visits(views: list[PageView]) -> list[list[PageView]]:
    """Split one person's views (oldest first) into visits."""
    out: list[list[PageView]] = []
    last_end = None
    for v in views:
        if last_end is None or v.created_at - last_end > VISIT_GAP:
            out.append([])
            last_end = v.created_at
        out[-1].append(v)
        last_end = max(last_end, v.created_at + timedelta(seconds=v.duration_s or 0))
    return out


def visit_stats(views: QuerySet) -> dict:
    """Visits, average time per visit and bounce rate (one page, nothing done)."""
    acted = set(Action.objects.filter(view__in=views).values_list("view_id", flat=True))
    by_person: dict[tuple, list[PageView]] = defaultdict(list)
    rows = views.only("id", "user_id", "visitor", "created_at", "duration_s").order_by("created_at")
    for v in rows:
        by_person[(person_key(v), timezone.localdate(v.created_at, league_tz()))].append(v)
    count = bounced = seconds = 0
    for person_views in by_person.values():
        for visit in visits(person_views):
            count += 1
            seconds += sum(v.duration_s or 0 for v in visit)
            if len(visit) == 1 and visit[0].id not in acted:
                bounced += 1
    return {
        "visits": count,
        "avg_visit_s": round(seconds / count) if count else 0,
        "bounce_rate": round(100 * bounced / count) if count else 0,
    }


def top_actions(actions: QuerySet, limit: int = TOP) -> list[dict]:
    rows = (
        actions.values("name")
        .annotate(times=Count("id"), people=Count("view__visitor", distinct=True))
        .order_by("-times", "name")[:limit]
    )
    return [{"name": r["name"], "times": r["times"], "people": r["people"]} for r in rows]


def _pages(views: QuerySet) -> list[dict]:
    rows = (
        views.values("path")
        .annotate(
            views=Count("id"),
            visitors=Count("visitor", distinct=True),
            seconds=Sum("duration_s"),
            timed=Count("duration_s"),
        )
        .order_by("-views", "path")[:TOP]
    )
    return [
        {"path": r["path"], "name": page_name(r["path"]), "views": r["views"],
         "visitors": r["visitors"],
         "avg_s": round((r["seconds"] or 0) / r["timed"]) if r["timed"] else 0}
        for r in rows
    ]  # fmt: skip


def day(on: date, who: str = "everyone") -> dict:
    """Everything about one day: numbers, hours, pages, actions and everyone who came."""
    start, end = day_bounds(on)
    with timezone.override(league_tz()):
        views = who_filter(PageView.objects.filter(created_at__gte=start, created_at__lt=end), who)
        actions = Action.objects.filter(view__in=views)
        hours = dict(
            views.annotate(hour=ExtractHour("created_at")).values("hour")
            .annotate(n=Count("id")).values_list("hour", "n")
        )  # fmt: skip
        action_hours = dict(
            actions.annotate(hour=ExtractHour("created_at")).values("hour")
            .annotate(n=Count("id")).values_list("hour", "n")
        )  # fmt: skip

    people: dict[str, dict] = {}
    all_views = list(views.select_related("user").order_by("created_at"))
    teams = _teams({v.user_id for v in all_views if v.user_id})
    counts = dict(actions.values("view_id").annotate(n=Count("id")).values_list("view_id", "n"))
    for v in all_views:
        key = person_key(v)
        p = people.get(key)
        if p is None:
            p = people[key] = {
                **describe(v, teams), "device": v.device, "browser": v.browser, "os": v.os,
                "source": v.source, "first": v.created_at, "last": v.created_at, "pages": 0,
                "actions": 0, "seconds": 0, "_views": [],
            }  # fmt: skip
        p["last"] = v.created_at
        p["pages"] += 1
        p["actions"] += counts.get(v.id, 0)
        p["seconds"] += v.duration_s or 0
        p["source"] = p["source"] or v.source
        p["_views"].append(v)
    for p in people.values():
        p["visits"] = len(visits(p.pop("_views")))
        p["first"] = p["first"].isoformat()
        p["last"] = p["last"].isoformat()

    stats = visit_stats(views)
    return {
        "date": on.isoformat(),
        "who": who,
        "totals": {
            "views": len(all_views),
            "people": len(people),
            "signed_in": sum(1 for p in people.values() if p["signed_in"]),
            "actions": actions.count(),
            "seconds": sum(p["seconds"] for p in people.values()),
            **stats,
        },
        "hours": [
            {"hour": h, "views": hours.get(h, 0), "actions": action_hours.get(h, 0)}
            for h in range(24)
        ],
        "pages": _pages(views),
        "actions": top_actions(actions),
        "people": sorted(people.values(), key=lambda p: p["first"]),
    }


def timeline(person: str, on: date) -> dict | None:
    """One person's day: each page in order with how long they stayed and what they did."""
    start, end = day_bounds(on)
    views = PageView.objects.filter(created_at__gte=start, created_at__lt=end)
    if person.startswith("u") and person[1:].isdigit():
        views = views.filter(user_id=int(person[1:]))
    elif person.startswith("v") and len(person) > 1:
        views = views.filter(visitor=person[1:], user__isnull=True)
    else:
        return None
    views = list(views.select_related("user").prefetch_related("actions").order_by("created_at"))
    if not views:
        return None
    teams = _teams({views[0].user_id} if views[0].user_id else set())
    out_visits = []
    for visit in visits(views):
        out_visits.append({
            "start": visit[0].created_at.isoformat(),
            "seconds": sum(v.duration_s or 0 for v in visit),
            "pages": [
                {"at": v.created_at.isoformat(), "path": v.path, "name": page_name(v.path),
                 "seconds": v.duration_s, "source": v.source,
                 "actions": [{"at": a.created_at.isoformat(), "name": a.name, "detail": a.detail}
                             for a in v.actions.all()]}
                for v in visit
            ],
        })  # fmt: skip
    first = views[0]
    return {
        "date": on.isoformat(),
        "person": {
            **describe(first, teams),
            "device": first.device,
            "browser": first.browser,
            "os": first.os,
        },  # fmt: skip
        "visits": out_visits,
    }


def people(days: int = 30) -> dict:
    """Every signed-in account seen in the last ``days`` days."""
    tz = league_tz()
    since = day_bounds(timezone.localdate(timezone=tz) - timedelta(days=days - 1))[0]
    views = PageView.objects.filter(created_at__gte=since, user__isnull=False)
    with timezone.override(tz):
        rows = (
            views.values("user_id", "user__email", "user__display_name")
            .annotate(
                pages=Count("id"), seconds=Sum("duration_s"), last=Max("created_at"),
                days=Count(TruncDate("created_at"), distinct=True), staff=Max("audience"),
            )
            .order_by("-last")
        )  # fmt: skip
        rows = list(rows)
        per_day = defaultdict(list)
        for user_id, d, n in (
            views.annotate(d=TruncDate("created_at")).values("user_id", "d")
            .annotate(n=Count("id")).values_list("user_id", "d", "n")
        ):  # fmt: skip
            per_day[user_id].append({"date": d.isoformat(), "pages": n})
    acted = dict(
        Action.objects.filter(view__in=views).values("view__user_id")
        .annotate(n=Count("id")).values_list("view__user_id", "n")
    )  # fmt: skip
    first_seen = dict(
        PageView.objects.filter(user_id__in=[r["user_id"] for r in rows])
        .values("user_id").annotate(f=Min("created_at")).values_list("user_id", "f")
    )  # fmt: skip
    teams = _teams([r["user_id"] for r in rows])
    return {
        "days": days,
        "people": [
            {
                "key": f"u{r['user_id']}",
                "name": r["user__display_name"] or r["user__email"],
                "team": teams.get(r["user_id"], ""),
                "staff": r["staff"] == "staff",
                "new": bool(first_seen.get(r["user_id"]) and first_seen[r["user_id"]] >= since),
                "pages": r["pages"],
                "actions": acted.get(r["user_id"], 0),
                "seconds": r["seconds"] or 0,
                "days_active": r["days"],
                "last": r["last"].isoformat(),
                "by_day": sorted(per_day[r["user_id"]], key=lambda x: x["date"], reverse=True),
            }
            for r in rows
        ],
    }


def actions_report(start: datetime, end: datetime, who: str, path: str = "") -> dict:
    """Each kind of action: how often, by how many people, on which pages, per day."""
    views = who_filter(PageView.objects.filter(created_at__gte=start, created_at__lte=end), who)
    if path:
        views = views.filter(path=path)
    actions = Action.objects.filter(view__in=views)
    with timezone.override(league_tz()):
        by_day = {
            d: n for d, n in actions.annotate(d=TruncDate("created_at")).values("d")
            .annotate(n=Count("id")).values_list("d", "n")
        }  # fmt: skip
    details = defaultdict(list)
    for name, detail, n in (
        actions.exclude(detail="").values("name", "detail").annotate(n=Count("id"))
        .order_by("-n").values_list("name", "detail", "n")
    ):  # fmt: skip
        if len(details[name]) < 5:
            details[name].append({"detail": detail, "times": n})
    pages = actions.values("view__path").annotate(n=Count("id")).order_by("-n")[:TOP]
    rows = top_actions(actions, limit=100)
    for r in rows:
        r["details"] = details.get(r["name"], [])
    first = timezone.localdate(start, league_tz())
    last = timezone.localdate(end, league_tz())
    series, d = [], first
    while d <= last:
        series.append({"date": d.isoformat(), "actions": by_day.get(d, 0)})
        d += timedelta(days=1)
    return {
        "who": who,
        "path": path,
        "total": actions.count(),
        "actions": rows,
        "by_day": series,
        "pages": [
            {"path": p["view__path"], "name": page_name(p["view__path"]), "actions": p["n"]}
            for p in pages
        ],  # fmt: skip
    }
