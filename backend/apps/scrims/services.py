"""The rules of scrim registration. Views and the predictions hook-up call only these.

- Scrim nights are the weekdays in ``ScrimSettings`` (Mon, Tue, Thu, Fri) minus skipped dates.
- Sign-up for both sessions opens at 12:01 Lagos time that day and closes at 6:00pm (8PM)
  and 8:00pm (10PM). A team's managers can register or withdraw while it's open.
- Up to ``max_teams`` (12) teams play; later teams join a waitlist and move up, in sign-up
  order, when a place frees before close. At close, waitlisted teams aren't playing.
- Suspended teams can't register, and suspending a team takes it out of every session that
  hasn't started.
- Staff can add or remove a team for one session at any time, past the cap and for a
  suspended team.

Every change is logged (``ScrimLog``), and ``lobby_changed`` is sent after a session's
playing teams change so predictions can follow.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.dispatch import Signal
from django.utils import timezone

from apps.league.models import Team

from .models import Registration, ScrimLog, ScrimSession, ScrimSettings, Suspension

R, A = Registration.Status, ScrimLog.Action
SESSIONS = {"8PM": dt.time(20), "10PM": dt.time(22)}

# Sent (after commit) with ``scrim`` whenever a session's playing teams change.
lobby_changed = Signal()


class ScrimError(Exception):
    """A rule stopped the change; the message is shown to the person as it is."""


# -- time ------------------------------------------------------------------------------------------


def local_tz() -> ZoneInfo:
    return ZoneInfo(settings.ANALYTICS_TIME_ZONE)


def now() -> dt.datetime:
    return timezone.localtime(timezone.now(), local_tz())


def today() -> dt.date:
    return now().date()


def clock(moment: dt.datetime) -> str:
    """12:01pm, 6:00pm."""
    return moment.strftime("%I:%M%p").lstrip("0").lower()


def is_scrim_night(date: dt.date, conf: ScrimSettings | None = None) -> bool:
    conf = conf or ScrimSettings.get()
    return date.weekday() in (conf.weekdays or []) and date.isoformat() not in (
        conf.skip_dates or []
    )


def next_scrim_night(conf: ScrimSettings | None = None, start: dt.date | None = None):
    """Today if it's a scrim night, else the next one within two weeks (or None)."""
    conf = conf or ScrimSettings.get()
    day = start or today()
    for _ in range(15):
        if is_scrim_night(day, conf):
            return day
        day += dt.timedelta(days=1)
    return None


def _at(date: dt.date, time: dt.time) -> dt.datetime:
    return dt.datetime.combine(date, time, tzinfo=local_tz())


def starts_at(date: dt.date, session: str) -> dt.datetime:
    return _at(date, SESSIONS[session])


def opens_at(date: dt.date, conf: ScrimSettings | None = None) -> dt.datetime:
    conf = conf or ScrimSettings.get()
    return _at(date, conf.opens_at)


def closes_at(date: dt.date, session: str, conf: ScrimSettings | None = None) -> dt.datetime:
    conf = conf or ScrimSettings.get()
    raw = (conf.closes_at or {}).get(session)
    try:
        time = dt.time.fromisoformat(raw)
    except (TypeError, ValueError):
        time = (dt.datetime.combine(date, SESSIONS[session]) - dt.timedelta(hours=2)).time()
    return _at(date, time)


def stage(date: dt.date, session: str, conf: ScrimSettings | None = None) -> str:
    """Where sign-up is: ``off`` (no scrims that night), ``soon``, ``open``, ``closed``
    (sign-up over, not started) or ``started``."""
    conf = conf or ScrimSettings.get()
    if not is_scrim_night(date, conf):
        return "off"
    moment = now()
    if moment >= starts_at(date, session):
        return "started"
    if moment >= closes_at(date, session, conf):
        return "closed"
    if moment >= opens_at(date, conf):
        return "open"
    return "soon"


# -- records ---------------------------------------------------------------------------------------


def get_session(date: dt.date, session: str) -> ScrimSession:
    if session not in SESSIONS:
        raise ScrimError("Sessions are 8PM and 10PM.")
    scrim, _ = ScrimSession.objects.get_or_create(
        date=date, session=session, defaults={"max_teams": ScrimSettings.get().max_teams}
    )
    return scrim


def active_suspension(team: Team) -> Suspension | None:
    return active_suspensions().filter(team=team).first()


def active_suspensions():
    return Suspension.objects.filter(ended_at__isnull=True).filter(
        Q(until__isnull=True) | Q(until__gte=today())
    )


def lobby(scrim: ScrimSession) -> list[int]:
    """The teams playing, as ids, in sign-up order."""
    return list(scrim.registrations.filter(status=R.REGISTERED).values_list("team_id", flat=True))


def _log(scrim, team, action, actor=None, note="") -> None:
    ScrimLog.objects.create(scrim=scrim, team=team, action=action, actor=actor, note=note)


def _changed(scrim: ScrimSession) -> None:
    transaction.on_commit(lambda: lobby_changed.send(sender=ScrimSession, scrim=scrim))


def _locked(scrim: ScrimSession) -> ScrimSession:
    """The session row, locked until the transaction ends, so two sign-ups at once can't both
    take the last place."""
    return ScrimSession.objects.select_for_update().get(pk=scrim.pk)


def _fill(scrim: ScrimSession, actor=None) -> bool:
    """Move waitlisted teams up, oldest first, while places are free. Only before close."""
    if stage(scrim.date, scrim.session) != "open":
        return False
    playing = scrim.registrations.filter(status=R.REGISTERED).count()
    moved = False
    for row in scrim.registrations.filter(status=R.WAITLIST).order_by("created_at", "pk"):
        if playing >= scrim.max_teams:
            break
        row.status = R.REGISTERED
        row.save(update_fields=["status", "updated_at"])
        _log(scrim, row.team, A.MOVED_UP, actor)
        playing += 1
        moved = True
    return moved


# -- teams -----------------------------------------------------------------------------------------


def register(scrim: ScrimSession, team: Team, user) -> Registration:
    """A team's manager signs the team up: a place if one is free, else the waitlist."""
    where = stage(scrim.date, scrim.session)
    if where == "off":
        raise ScrimError("There are no scrims that night.")
    if where == "soon":
        raise ScrimError(f"Sign-up opens at {clock(opens_at(scrim.date))}.")
    if where in ("closed", "started"):
        raise ScrimError("Sign-up for this session has closed.")
    held = active_suspension(team)
    if held:
        why = f" Reason: {held.reason}" if held.reason else ""
        raise ScrimError(f"{team.name} is suspended and can't register.{why}")
    with transaction.atomic():
        scrim = _locked(scrim)
        if scrim.registrations.filter(team=team).exists():
            raise ScrimError(f"{team.name} is already signed up for this session.")
        playing = scrim.registrations.filter(status=R.REGISTERED).count()
        status = R.REGISTERED if playing < scrim.max_teams else R.WAITLIST
        row = Registration.objects.create(scrim=scrim, team=team, status=status, registered_by=user)
        _log(scrim, team, A.REGISTERED if status == R.REGISTERED else A.WAITLISTED, user)
        if status == R.REGISTERED:
            _changed(scrim)
    return row


def withdraw(scrim: ScrimSession, team: Team, user) -> None:
    """A team's manager takes the team out before sign-up closes."""
    if stage(scrim.date, scrim.session) != "open":
        raise ScrimError("Sign-up has closed, so only staff can change this session now.")
    with transaction.atomic():
        scrim = _locked(scrim)
        row = scrim.registrations.filter(team=team).first()
        if row is None:
            raise ScrimError(f"{team.name} isn't signed up for this session.")
        was_playing = row.status == R.REGISTERED
        row.delete()
        _log(scrim, team, A.WITHDREW, user)
        if was_playing:
            _fill(scrim, user)
            _changed(scrim)


# -- staff -----------------------------------------------------------------------------------------


def staff_add(scrim: ScrimSession, team: Team, actor, note: str = "") -> Registration:
    """Put a team in a session's playing list, at any time, past the cap or a suspension."""
    with transaction.atomic():
        scrim = _locked(scrim)
        row = scrim.registrations.filter(team=team).first()
        if row and row.status == R.REGISTERED:
            raise ScrimError(f"{team.name} is already playing in this session.")
        if row:
            row.status = R.REGISTERED
            row.by_staff = True
            row.save(update_fields=["status", "by_staff", "updated_at"])
        else:
            row = Registration.objects.create(
                scrim=scrim, team=team, status=R.REGISTERED, by_staff=True, registered_by=actor
            )
        _log(scrim, team, A.STAFF_ADDED, actor, note)
        _changed(scrim)
    return row


def staff_remove(scrim: ScrimSession, team: Team, actor, note: str = "") -> None:
    """Take a team out of a session (playing or waitlisted), at any time."""
    with transaction.atomic():
        scrim = _locked(scrim)
        row = scrim.registrations.filter(team=team).first()
        if row is None:
            raise ScrimError(f"{team.name} isn't in this session.")
        was_playing = row.status == R.REGISTERED
        row.delete()
        _log(scrim, team, A.STAFF_REMOVED, actor, note)
        if was_playing:
            _fill(scrim, actor)
            _changed(scrim)


def set_max_teams(scrim: ScrimSession, max_teams: int, actor) -> ScrimSession:
    """Change a session's places. More places move waitlisted teams up (before close); fewer
    never push out a team that already has a place."""
    if not 2 <= max_teams <= 50:
        raise ScrimError("A session needs 2 to 50 places.")
    with transaction.atomic():
        scrim = _locked(scrim)
        scrim.max_teams = max_teams
        scrim.save(update_fields=["max_teams"])
        if _fill(scrim, actor):
            _changed(scrim)
    return scrim


def suspend(team: Team, actor, reason: str = "", until: dt.date | None = None) -> Suspension:
    """Stop a team registering, and take it out of every session that hasn't started."""
    if until is not None and until < today():
        raise ScrimError("The end date has passed.")
    with transaction.atomic():
        if active_suspension(team):
            raise ScrimError(f"{team.name} is already suspended.")
        held = Suspension.objects.create(team=team, reason=reason, until=until, started_by=actor)
        _log(None, team, A.SUSPENDED, actor, reason)
        rows = Registration.objects.filter(team=team, scrim__date__gte=today()).select_related(
            "scrim"
        )
        for row in rows:
            scrim = row.scrim
            if now() >= starts_at(scrim.date, scrim.session):
                continue
            scrim = _locked(scrim)
            was_playing = row.status == R.REGISTERED
            row.delete()
            _log(scrim, team, A.SUSPENDED_OUT, actor)
            if was_playing:
                _fill(scrim, actor)
                _changed(scrim)
    return held


def unsuspend(team: Team, actor) -> Suspension:
    held = active_suspension(team)
    if held is None:
        raise ScrimError(f"{team.name} isn't suspended.")
    held.ended_at = timezone.now()
    held.ended_by = actor
    held.save(update_fields=["ended_at", "ended_by"])
    _log(None, team, A.UNSUSPENDED, actor)
    return held
