"""Linking fixtures to uploaded matches and settling markets by themselves.

When staff upload a match and it is published, the site finds the fixture it is about:

- the session (8PM or 10PM) from the match day's name ("TDL DAY 12 8PM"),
- the date from the match day,
- the match number within the day.

It links that fixture (and the session's fixture to the match day), then settles every
closed market whose result the logs decide, exactly as staff would by pressing "Confirm
result" on the suggestion. Anything it can't be sure about is left for staff with a note
(``attention``) and shown on Staff > Predictions under "Needs you":

- the match day name doesn't say which session, or the match started outside the session;
- the fixture is already linked to another match;
- a team in the lobby didn't play while a team outside it did (a rename or duplicate team);
- a session with fewer than 5 published matches (staff settle it by hand if that's all);
- a result that changed after a re-upload: settled markets are never changed by themselves.

A task runs this every 5 minutes as well, so nothing is missed. Settling uses the same
``settle`` / ``void`` as staff, so a repeat never pays twice.
"""

from __future__ import annotations

import datetime as dt
import logging
import re

from django.conf import settings
from django.db.models import Exists, F, Max, OuterRef, Q
from django.utils import timezone

from apps.league.models import Match, MatchDay, Team
from apps.results.models import TeamMatchResult

from . import auto
from .markets import RANGE_MARKETS, SEASON_MARKETS, SESSION_MARKETS, MarketError
from .models import AutoSettings, Fixture, Market
from .settlement import settle, suggest, void

log = logging.getLogger(__name__)

S = Market.Status
SESSION_IN_NAME = re.compile(r"(?<!\d)(8|10)\s*PM\b", re.IGNORECASE)
EARLY = dt.timedelta(minutes=45)  # a match may start this long before its session
LATE = dt.timedelta(hours=4)  # ... and this long after the session's start
CHASE_AFTER = dt.timedelta(hours=6)  # from session start: missing uploads become "Needs you"
RANGE_GRACE = dt.timedelta(days=2)  # date-range markets settle by then whatever is missing
LOOK_BACK = dt.timedelta(days=21)  # fixtures older than this are left alone
AUTO_REFERENCE = "Settled automatically from the uploaded logs"
CHANGED = "The results changed after it was settled (re-upload). Check it and correct it."


def is_on() -> bool:
    return settings.PREDICTIONS_ENABLED and AutoSettings.get().settle_enabled


# -- which session and date a match day is -------------------------------------------------------


def session_of(day: MatchDay) -> str | None:
    """8PM or 10PM from the match day's name; None when it names neither or both."""
    found = {f"{n}PM" for n in SESSION_IN_NAME.findall(day.title or "")}
    return found.pop() if len(found) == 1 else None


def date_of(day: MatchDay) -> dt.date | None:
    """The night a match day was played: its date, else when its first match started."""
    if day.date:
        return day.date
    starts = [m.started_at for m in day.matches.all() if m.started_at]
    if not starts:
        return None
    return timezone.localtime(min(starts), auto.local_tz()).date()


def _flag(obj, note: str) -> None:
    note = note[:300]
    if obj.attention != note:
        obj.attention = note
        type(obj).objects.filter(pk=obj.pk).update(attention=note)


# -- linking -------------------------------------------------------------------------------------


def link_match(match: Match) -> str:
    """Link the fixture about ``match`` (and its session's fixture to the match day).
    Returns what happened, for the report."""
    if match.status != Match.Status.PUBLISHED:
        return f"{match}: not published yet."
    if Fixture.objects.filter(match=match).exists():
        return f"{match}: already linked."
    day = match.match_day
    season_id = day.stage.season_id
    date, session = date_of(day), session_of(day)
    if date is None or session is None:
        why = "doesn't say 8PM or 10PM" if session is None else "has no date"
        note = f"Uploaded {match} couldn't be placed: its match day name {why}. Link it by hand."
        if date is not None:
            for f in Fixture.objects.filter(
                season_id=season_id, date=date, match_number=match.number, match__isnull=True
            ):
                _flag(f, note)
        return note
    fixture = Fixture.objects.filter(
        season_id=season_id, date=date, session=session, match_number=match.number
    ).first()
    if fixture is None:
        return f"{match}: no predictions on it."
    rivals = [d for d in _days_on(season_id, date) if d.pk != day.pk and session_of(d) == session]
    if rivals:
        _flag(
            fixture,
            f"More than one {session} match day on {date:%d %b} ({day}, {rivals[0]}), so it "
            "wasn't linked. Link it by hand.",
        )
        return f"{match}: two {session} match days that night."
    if fixture.match_id is not None:
        _flag(
            fixture,
            f"Already linked to another match, and {match} was uploaded for it too. "
            "Check which one is right.",
        )
        return f"{match}: its fixture is linked to another match."
    start = auto.session_start(date, session)
    if match.started_at and not (start - EARLY <= match.started_at <= start + LATE):
        at = timezone.localtime(match.started_at, auto.local_tz())
        note = (
            f"{match} started at {at:%H:%M %d %b}, outside the {session} session, so it "
            "wasn't linked. Link it by hand if it's right."
        )
        _flag(fixture, note)
        return note
    fixture.match, fixture.attention = match, ""
    fixture.save(update_fields=["match", "attention", "updated_at"])
    _link_day(season_id, date, session, day)
    return f"{match}: linked to {fixture}."


def _days_on(season_id: int, date: dt.date) -> list[MatchDay]:
    days = (
        MatchDay.objects.filter(stage__season=season_id)
        .filter(Q(date=date) | Q(date__isnull=True, matches__started_at__date__gte=date))
        .distinct()
        .prefetch_related("matches")
    )
    return [d for d in days if date_of(d) == date]


def _link_day(season_id: int, date: dt.date, session: str, day: MatchDay) -> None:
    whole = Fixture.objects.filter(
        season_id=season_id, date=date, session=session, match_number__isnull=True
    ).first()
    if whole is None:
        return
    if whole.match_day_id is None:
        if Fixture.objects.filter(match_day=day).exclude(pk=whole.pk).exists():
            _flag(whole, f"{day} is already linked to another session. Link it by hand.")
            return
        whole.match_day, whole.attention = day, ""
        whole.save(update_fields=["match_day", "attention", "updated_at"])
    elif whole.match_day_id != day.pk:
        _flag(
            whole,
            f"This session's matches were uploaded to more than one match day ({day} too). "
            "Check which one is right.",
        )


def link_recent(now=None) -> list[str]:
    """Link every recent published match that no fixture points at yet."""
    now = now or timezone.now()
    since = (now - LOOK_BACK).date()
    linked = Fixture.objects.filter(match__isnull=False).values("match")
    matches = (
        Match.objects.filter(status=Match.Status.PUBLISHED)
        .filter(Q(match_day__date__gte=since) | Q(started_at__gte=now - LOOK_BACK))
        .exclude(pk__in=linked)
        .select_related("match_day__stage")
        .order_by("match_day", "number")
    )
    notes = [link_match(m) for m in matches]
    _chase_missing(now)
    return notes


def _chase_missing(now) -> None:
    """Fixtures still waiting for their match well after the session: tell staff."""
    since = (now - LOOK_BACK).date()
    waiting = Fixture.objects.filter(
        date__gte=since, match_number__isnull=False, match__isnull=True, attention=""
    ).filter(markets__status__in=[S.OPEN, S.SUSPENDED, S.CLOSED])
    for f in waiting.distinct():
        if f.session not in auto.SESSIONS:
            continue
        if now >= auto.session_start(f.date, f.session) + CHASE_AFTER:
            _flag(
                f,
                f"Match {f.match_number} isn't uploaded or linked yet. Upload it, link it by "
                "hand, or refund it (Refund session) if it wasn't played.",
            )


# -- settling ------------------------------------------------------------------------------------


def _lobby_mismatch(market: Market) -> str | None:
    """A lobby team didn't play while a team outside the lobby did: likely a renamed or
    duplicate team, so the site doesn't refund or settle on its own."""
    fixture = market.fixture
    if fixture is None:
        return None
    whole = (
        fixture
        if fixture.match_number is None
        else Fixture.objects.filter(
            season_id=fixture.season_id,
            date=fixture.date,
            session=fixture.session,
            match_number__isnull=True,
        ).first()
    )
    lobby = set(whole.teams.values_list("pk", flat=True)) if whole else set()
    if not lobby:
        return None
    if fixture.match_number is not None:
        results = TeamMatchResult.objects.filter(match=fixture.match_id)
    else:
        results = TeamMatchResult.objects.filter(
            match__match_day=fixture.match_day_id, match__status=Match.Status.PUBLISHED
        )
    played = dict(results.values_list("team_id", "team__name"))
    missing = lobby - set(played)
    extra = set(played) - lobby
    if not (missing and extra):
        return None
    gone = ", ".join(sorted(Team.objects.filter(pk__in=missing).values_list("name", flat=True)))
    new = ", ".join(sorted(played[t] for t in extra))
    return (
        f"{gone} didn't play but {new} did (not signed up). If it's the same team, merge or "
        "fix the team and re-upload; otherwise confirm the result by hand."
    )


def _session_ready(market: Market, now) -> str | None:
    """Session markets wait for all 5 matches; returns why they're waiting (or None)."""
    fixture = market.fixture
    published = Match.objects.filter(
        match_day=fixture.match_day_id, status=Match.Status.PUBLISHED
    ).count()
    if published >= auto.MATCHES:
        return None
    if fixture.session in auto.SESSIONS and now >= (
        auto.session_start(fixture.date, fixture.session) + CHASE_AFTER
    ):
        return (
            f"Only {published} of {auto.MATCHES} matches are published. Upload the rest, or "
            "confirm the result by hand if that's all that was played."
        )
    return ""  # still uploading: wait quietly


def _range_ready(market: Market, now) -> bool:
    """A date-range market waits for every session in its dates to be uploaded (or 2 days)."""
    end = dt.date.fromisoformat(market.params["to"])
    end_at = dt.datetime.combine(end + dt.timedelta(days=1), dt.time(), tzinfo=auto.local_tz())
    if now < end_at:
        return False
    if now >= end_at + RANGE_GRACE:
        return True
    sessions = Fixture.objects.filter(
        season_id=market.season_id,
        date__gte=market.params["from"],
        date__lte=end,
        match_number__isnull=True,
    )
    for whole in sessions:
        if whole.match_day_id is None:
            return False
        published = Match.objects.filter(
            match_day=whole.match_day_id, status=Match.Status.PUBLISHED
        ).count()
        if published < auto.MATCHES:
            return False
    return True


def settle_market(market: Market, actor, now=None) -> str:
    """Settle one CLOSED market from the logs if nothing needs a person. Returns
    "settled", "voided", "waiting" or "flagged"."""
    now = now or timezone.now()
    if market.category in RANGE_MARKETS:
        if not _range_ready(market, now):
            return "waiting"
    elif market.category in SEASON_MARKETS:
        return "waiting"  # the season's end is staff's call
    elif market.fixture is None:
        return "waiting"
    elif market.category in SESSION_MARKETS:
        if market.fixture.match_day_id is None:
            return "waiting"
        why = _session_ready(market, now)
        if why is not None:
            if why:
                _flag(market, why)
                return "flagged"
            return "waiting"
    elif market.fixture.match_id is None:
        return "waiting"
    try:
        suggestion = suggest(market)
    except MarketError as exc:
        if exc.code == "not_ready":
            return "waiting"
        _flag(market, f"{exc} Confirm the result by hand.")
        return "flagged"
    except Exception:  # noqa: BLE001 - one odd market must not stop the rest
        log.exception("Couldn't work out market %s", market.pk)
        _flag(market, "The site couldn't work out this result. Confirm it by hand.")
        return "flagged"
    if why := _lobby_mismatch(market):
        _flag(market, why)
        return "flagged"
    try:
        if suggestion["kind"] == "VOID":
            void(
                market,
                actor=actor,
                reason=suggestion["note"] or "Refunded: no result.",
                reference=AUTO_REFERENCE,
            )
            result = "voided"
        else:
            settle(
                market,
                actor=actor,
                winners=suggestion["winners"],
                voids=suggestion["voids"],
                dead_heat=suggestion.get("dead_heat", 1),
                reference=AUTO_REFERENCE,
            )
            result = "settled"
    except MarketError as exc:
        _flag(market, f"{exc} Confirm the result by hand.")
        return "flagged"
    if market.attention:
        _flag(market, "")
    return result


def _same_as(latest, suggestion: dict) -> bool:
    if suggestion["kind"] != latest.kind:
        return False
    if latest.kind == "VOID":
        return True
    return (
        set(latest.winning_outcomes.values_list("pk", flat=True)) == set(suggestion["winners"])
        and set(latest.void_outcomes.values_list("pk", flat=True)) == set(suggestion["voids"])
        and latest.dead_heat == suggestion.get("dead_heat", 1)
    )


def _match_changed_at(market: Market):
    fixture = market.fixture
    if fixture is None:
        return None
    if fixture.match_number is not None:
        return fixture.match.updated_at if fixture.match_id else None
    if fixture.match_day_id:
        return Match.objects.filter(match_day=fixture.match_day_id).aggregate(t=Max("updated_at"))[
            "t"
        ]
    return None


def check_settled(market: Market) -> bool:
    """After a re-upload: flag a settled market whose result the logs no longer give.
    Never changes coins. Returns True when flagged."""
    latest = market.settlements.order_by("-version").first()
    changed_at = _match_changed_at(market)
    if latest is None or changed_at is None:
        return False
    try:
        suggestion = suggest(market)
    except MarketError:
        return market.attention == CHANGED
    if _same_as(latest, suggestion) or latest.created_at >= changed_at:
        # Same result, or staff decided after the latest upload (a correction or override).
        if market.attention == CHANGED:
            _flag(market, "")
        return False
    _flag(market, CHANGED)
    return True


def settle_recent(now=None, actor=None) -> dict:
    now = now or timezone.now()
    actor = actor or auto.system_user()
    since = (now - LOOK_BACK).date()
    counts = {"settled": 0, "voided": 0, "waiting": 0, "flagged": 0, "changed": 0}
    recent = Q(fixture__date__gte=since) | Q(
        fixture__isnull=True,
        category__in=RANGE_MARKETS,
        closes_at__gte=now - LOOK_BACK - RANGE_GRACE,
    )
    closed = Market.objects.filter(recent, status=S.CLOSED).select_related("fixture")
    for market in closed.order_by("closes_at", "pk"):
        counts[settle_market(market, actor, now)] += 1
    # Only markets whose match (or session) was rebuilt after the market last changed.
    rebuilt_day = Match.objects.filter(
        match_day=OuterRef("fixture__match_day"), updated_at__gt=OuterRef("updated_at")
    )
    done = (
        Market.objects.filter(fixture__date__gte=since, status__in=[S.SETTLED, S.VOID])
        .filter(
            Q(attention=CHANGED)
            | Q(fixture__match_number__isnull=False, fixture__match__updated_at__gt=F("updated_at"))
            | Q(fixture__match_number__isnull=True, fixture__match_day__isnull=False)
            & Exists(rebuilt_day)
        )
        .select_related("fixture__match")
    )
    for market in done:
        counts["changed"] += check_settled(market)
    return counts


def run(match_id: int | None = None, *, force: bool = False, actor=None) -> dict:
    """Link and settle what the uploads allow. ``force`` ignores the switch (staff button)."""
    if not force and not is_on():
        return {"linked": [], "markets": {}, "off": True}
    notes = []
    if match_id is not None:
        match = Match.objects.filter(pk=match_id).select_related("match_day__stage").first()
        if match is not None:
            notes.append(link_match(match))
    notes += link_recent()
    return {"linked": notes, "markets": settle_recent(actor=actor)}


def needs_you() -> dict:
    """Everything the site left for staff, newest first."""
    since = (timezone.now() - LOOK_BACK).date()
    live = [S.OPEN, S.SUSPENDED, S.CLOSED]
    # A fixture only matters while it still has markets to settle.
    fixtures = (
        Fixture.objects.filter(date__gte=since, markets__status__in=live)
        .exclude(attention="")
        .distinct()
    )
    markets = (
        Market.objects.exclude(attention="")
        .filter(Q(status__in=live) | Q(attention=CHANGED))
        .filter(Q(fixture__date__gte=since) | Q(fixture__isnull=True))
        .select_related("fixture")
    )
    return {
        "fixtures": [
            {"id": f.pk, "title": str(f), "date": f.date, "note": f.attention}
            for f in fixtures.order_by("-date", "session", "match_number")
        ],
        "markets": [
            {
                "id": m.pk,
                "title": m.title,
                "status": m.status,
                "fixture": str(m.fixture) if m.fixture else None,
                "fixture_id": m.fixture_id,
                "note": m.attention,
            }
            for m in markets.order_by("-closes_at", "pk")
        ],
    }
