"""The rules of scrim registration. Views and the predictions hook-up call only these.

- Scrim nights are the weekdays in ``ScrimSettings`` (Mon, Tue, Thu, Fri) minus skipped dates.
- Sign-up for both sessions opens at 8:00pm Lagos time the day before (Thursday's opens
  Wednesday 8pm) and closes at 6:00pm (8PM) and 8:00pm (10PM) on the night. A team's
  managers, or any of its players with a linked game UID, can register or withdraw.
- Signing up costs ``ScrimSettings.fee`` DC (500), paid by whoever presses the button (staff
  pay nothing). It's refunded when the team withdraws, staff take it out, it's suspended out,
  or it ends sign-up still on the waitlist. A team that plays keeps it paid.
- Up to ``max_teams`` (12) teams play; later teams join a waitlist and move up, in sign-up
  order, when a place frees before close. When every place is taken the session **locks**:
  playing teams can't withdraw any more (only staff can change it) and predictions open
  straight away. Teams can still join the waitlist as backups.
- Staff can invite a team: its place is held until the team confirms (paying the fee) or
  declines. Invites not confirmed by close are dropped and the waitlist moves into the
  places; teams still waiting then are refunded (``wrap``).
- Suspended teams can't register, and suspending a team takes it out of every session that
  hasn't started.
- Staff can add or remove a team for one session at any time, past the cap and for a
  suspended team.

Every change is logged (``ScrimLog``), and ``lobby_changed`` is sent after a session's
playing teams change (or it locks) so predictions can follow.
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
HOLDS_PLACE = [R.REGISTERED, R.INVITED]

# Sent (after commit) with ``scrim`` whenever a session's playing teams change or it locks.
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


def when(moment: dt.datetime) -> str:
    """ "at 8:00pm" today, or "Wednesday at 8:00pm"."""
    if moment.date() == today():
        return f"at {clock(moment)}"
    return f"{moment:%A} at {clock(moment)}"


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


def shown_nights(conf: ScrimSettings | None = None) -> list[dt.date]:
    """The nights the pages show: tonight until its last session starts, and the next scrim
    night (once its sign-up has opened, or when there's nothing tonight)."""
    conf = conf or ScrimSettings.get()
    day, moment = today(), now()
    nights = []
    if is_scrim_night(day, conf) and moment < starts_at(day, "10PM"):
        nights.append(day)
    following = next_scrim_night(conf, day + dt.timedelta(days=1))
    if following and (not nights or moment >= opens_at(following, conf)):
        nights.append(following)
    return nights


def _at(date: dt.date, time: dt.time) -> dt.datetime:
    return dt.datetime.combine(date, time, tzinfo=local_tz())


def starts_at(date: dt.date, session: str) -> dt.datetime:
    return _at(date, SESSIONS[session])


def opens_at(date: dt.date, conf: ScrimSettings | None = None) -> dt.datetime:
    conf = conf or ScrimSettings.get()
    return _at(date - dt.timedelta(days=conf.opens_days_before or 0), conf.opens_at)


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
    (sign-up over, not started) or ``started``. A full session is still ``open`` (teams can
    join the waitlist) but ``locked``."""
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


# -- who -------------------------------------------------------------------------------------------


def is_linked_player(user, team: Team) -> bool:
    """A player on the team whose account is linked to their game UID."""
    player = getattr(user, "player", None) if user and user.is_authenticated else None
    if player is None:
        return False
    if player.current_team_id == team.pk:
        return True
    return user.memberships.filter(team=team, is_active=True).exists()


def can_register(user, team: Team) -> bool:
    """Staff, the team's managers, and its players with a linked game UID."""
    if not user or not user.is_authenticated:
        return False
    return bool(user.is_league_staff or user.manages(team) or is_linked_player(user, team))


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


def _taken(scrim: ScrimSession) -> int:
    """Places held: teams playing and teams invited."""
    return scrim.registrations.filter(status__in=HOLDS_PLACE).count()


# -- DC --------------------------------------------------------------------------------------------


def fee() -> int:
    return ScrimSettings.get().fee


def _pays(user) -> bool:
    """Staff sign teams up for free (they can't hold DC)."""
    return bool(user and user.is_authenticated and not user.is_league_staff)


def _charge(row: Registration, user) -> None:
    """Take the sign-up fee from the person signing the team up, once per place."""
    amount = fee()
    if row.fee_paid or amount <= 0 or not _pays(user):
        return
    from apps.predictions.models import LedgerEntry
    from apps.predictions.services import NotEnoughCoins, post_entry, wallet_for

    scrim = row.scrim
    try:
        post_entry(
            wallet_for(user), LedgerEntry.Kind.SCRIM_FEE, -amount, f"scrim-fee:{row.pk}",
            reason=f"{row.team.name}: {scrim.date:%a %d %b} {scrim.session} scrims", actor=user,
        )  # fmt: skip
    except NotEnoughCoins as exc:
        raise ScrimError(f"Signing up costs {amount:,} DC. {exc}") from exc
    row.fee_paid, row.paid_by = amount, user
    row.save(update_fields=["fee_paid", "paid_by", "updated_at"])


def _refund(row: Registration, actor=None, why: str = "") -> None:
    """Give the sign-up fee back to whoever paid it (once)."""
    if not row.fee_paid or row.paid_by_id is None:
        return
    from apps.predictions.models import LedgerEntry
    from apps.predictions.services import post_entry, wallet_for

    scrim = row.scrim
    _, made = post_entry(
        wallet_for(row.paid_by), LedgerEntry.Kind.SCRIM_REFUND, row.fee_paid,
        f"scrim-refund:{row.pk}",
        reason=f"{row.team.name}: {scrim.date:%a %d %b} {scrim.session} scrims. {why}".strip(),
        actor=actor,
    )  # fmt: skip
    if made:
        _log(scrim, row.team, A.REFUNDED, actor, f"{row.fee_paid:,} DC. {why}".strip())


def _drop(row: Registration, action, actor=None, note="", why="") -> bool:
    """Take a team out of a session, refunding its fee. True if it had a place."""
    had_place = row.status == R.REGISTERED
    _refund(row, actor, why)
    row.delete()
    _log(row.scrim, row.team, action, actor, note)
    return had_place


# -- filling and locking ---------------------------------------------------------------------------


def _fill(scrim: ScrimSession, actor=None, *, at_close: bool = False) -> bool:
    """Move waitlisted teams up, oldest first, while places are free. Only while sign-up is
    open (or once, as sign-up closes). In a locked session places only free up through staff,
    and the waitlist backs them up."""
    if not at_close and stage(scrim.date, scrim.session) != "open":
        return False
    free = scrim.max_teams - _taken(scrim)
    moved = False
    waiting = list(scrim.registrations.filter(status=R.WAITLIST).order_by("created_at", "pk"))
    # The week's DC priority team (most DC earned from matches last week) moves up first.
    from apps.dc.ranks import priority_team

    first = priority_team(scrim.date)
    if first:
        waiting.sort(key=lambda r: r.team_id != first["team_id"])
    for row in waiting:
        if free <= 0:
            break
        row.status = R.REGISTERED
        row.save(update_fields=["status", "updated_at"])
        _log(scrim, row.team, A.MOVED_UP, actor)
        free -= 1
        moved = True
    if moved and not at_close:
        _lock_if_full(scrim, actor)
    return moved


def _lock_if_full(scrim: ScrimSession, actor=None) -> bool:
    """Every place taken by a playing team: lock sign-up so predictions can open now."""
    if scrim.locked_at or stage(scrim.date, scrim.session) not in ("soon", "open"):
        return False
    playing = scrim.registrations.filter(status=R.REGISTERED).order_by("-updated_at", "-pk")
    if playing.count() < scrim.max_teams:
        return False
    scrim.locked_at = timezone.now()
    scrim.save(update_fields=["locked_at"])
    _log(scrim, playing[0].team, A.FILLED, actor)
    _changed(scrim)
    return True


def wrap(scrim: ScrimSession) -> bool:
    """Once sign-up has closed: drop invites nobody confirmed, move waitlisted teams into the
    free places, and refund the teams still waiting. Runs once per session. True if the
    playing teams changed."""
    if scrim.wrapped_at or stage(scrim.date, scrim.session) not in ("closed", "started"):
        return False
    with transaction.atomic():
        scrim = _locked(scrim)
        if scrim.wrapped_at:
            return False
        for row in scrim.registrations.filter(status=R.INVITED).select_related("team"):
            row.delete()
            _log(scrim, row.team, A.INVITE_EXPIRED)
        moved = stage(scrim.date, scrim.session) == "closed" and _fill(scrim, at_close=True)
        for row in scrim.registrations.filter(status=R.WAITLIST).select_related(
            "team", "paid_by", "scrim"
        ):
            _refund(row, why="Still on the waitlist when sign-up closed.")
        scrim.wrapped_at = timezone.now()
        scrim.save(update_fields=["wrapped_at"])
        if moved:
            _changed(scrim)
    return moved


def wrap_due() -> int:
    """Every few minutes: wrap the sessions whose sign-up has closed."""
    done = 0
    since = today() - dt.timedelta(days=2)
    for scrim in ScrimSession.objects.filter(wrapped_at__isnull=True, date__gte=since):
        if stage(scrim.date, scrim.session) in ("closed", "started"):
            wrap(scrim)
            done += 1
    return done


# -- teams -----------------------------------------------------------------------------------------


def _check_open(scrim: ScrimSession, *, early_ok: bool = False) -> None:
    where = stage(scrim.date, scrim.session)
    if where == "off":
        raise ScrimError("There are no scrims that night.")
    if where == "soon" and not early_ok:
        raise ScrimError(f"Sign-up opens {when(opens_at(scrim.date))}.")
    if where in ("closed", "started"):
        raise ScrimError("Sign-up for this session has closed.")


def _check_suspension(team: Team) -> None:
    held = active_suspension(team)
    if held:
        why = f" Reason: {held.reason}" if held.reason else ""
        raise ScrimError(f"{team.name} is suspended and can't register.{why}")


def register(scrim: ScrimSession, team: Team, user) -> Registration:
    """Someone on the team signs it up, paying the fee: a place if one is free, else the
    waitlist. A team staff invited confirms its place this way too."""
    if scrim.registrations.filter(team=team, status=R.INVITED).exists():
        return confirm(scrim, team, user)
    _check_open(scrim)
    _check_suspension(team)
    with transaction.atomic():
        scrim = _locked(scrim)
        if scrim.registrations.filter(team=team).exists():
            raise ScrimError(f"{team.name} is already signed up for this session.")
        free = not scrim.locked_at and _taken(scrim) < scrim.max_teams
        status = R.REGISTERED if free else R.WAITLIST
        row = Registration.objects.create(scrim=scrim, team=team, status=status, registered_by=user)
        _charge(row, user)
        _log(scrim, team, A.REGISTERED if status == R.REGISTERED else A.WAITLISTED, user)
        if status == R.REGISTERED:
            _changed(scrim)
            _lock_if_full(scrim, user)
    return row


def confirm(scrim: ScrimSession, team: Team, user) -> Registration:
    """A team staff invited takes its place, paying the fee. Allowed before sign-up opens."""
    _check_open(scrim, early_ok=True)
    _check_suspension(team)
    with transaction.atomic():
        scrim = _locked(scrim)
        row = scrim.registrations.filter(team=team, status=R.INVITED).first()
        if row is None:
            raise ScrimError(f"{team.name} has no invite for this session.")
        _charge(row, user)
        row.status = R.REGISTERED
        row.registered_by = user
        row.save(update_fields=["status", "registered_by", "updated_at"])
        _log(scrim, team, A.CONFIRMED, user)
        _changed(scrim)
        _lock_if_full(scrim, user)
    return row


def withdraw(scrim: ScrimSession, team: Team, user) -> None:
    """Someone on the team takes it out (or declines an invite) before sign-up closes. Once a
    session is full and locked, a playing team can only leave through staff."""
    with transaction.atomic():
        scrim = _locked(scrim)
        row = scrim.registrations.filter(team=team).select_related("team", "paid_by").first()
        if row is None:
            raise ScrimError(f"{team.name} isn't signed up for this session.")
        if row.status == R.INVITED:
            if stage(scrim.date, scrim.session) not in ("soon", "open"):
                raise ScrimError("Sign-up has closed, so only staff can change this session now.")
            _drop(row, A.DECLINED, user)
            _fill(scrim, user)
            return
        if stage(scrim.date, scrim.session) != "open":
            raise ScrimError("Sign-up has closed, so only staff can change this session now.")
        if row.status == R.REGISTERED and scrim.locked_at:
            raise ScrimError(
                "The session is full and predictions are open, so only staff can take a team "
                "out now."
            )
        if _drop(row, A.WITHDREW, user, why="Withdrew."):
            _fill(scrim, user)
            _changed(scrim)


# -- staff -----------------------------------------------------------------------------------------


def staff_add(scrim: ScrimSession, team: Team, actor, note: str = "") -> Registration:
    """Put a team in a session's playing list, at any time, past the cap or a suspension.
    Free: staff decide."""
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
        _lock_if_full(scrim, actor)
    return row


def staff_invite(scrim: ScrimSession, team: Team, actor, note: str = "") -> Registration:
    """Hold a place for a team until it confirms (paying the fee) or declines. Before close."""
    _check_open(scrim, early_ok=True)
    with transaction.atomic():
        scrim = _locked(scrim)
        row = scrim.registrations.filter(team=team).first()
        if row and row.status == R.REGISTERED:
            raise ScrimError(f"{team.name} is already playing in this session.")
        if row and row.status == R.INVITED:
            raise ScrimError(f"{team.name} is already invited.")
        if row:
            raise ScrimError(
                f"{team.name} is on the waitlist and has paid. Use Add to give it a place."
            )
        row = Registration.objects.create(
            scrim=scrim, team=team, status=R.INVITED, by_staff=True, registered_by=actor
        )
        _log(scrim, team, A.INVITED, actor, note)
    return row


def staff_remove(scrim: ScrimSession, team: Team, actor, note: str = "") -> None:
    """Take a team out of a session (playing, invited or waitlisted), at any time. Its fee
    is refunded."""
    with transaction.atomic():
        scrim = _locked(scrim)
        row = scrim.registrations.filter(team=team).select_related("team", "paid_by").first()
        if row is None:
            raise ScrimError(f"{team.name} isn't in this session.")
        held_place = row.status in HOLDS_PLACE
        if _drop(row, A.STAFF_REMOVED, actor, note, why="Removed by staff."):
            _changed(scrim)
        if held_place:
            _fill(scrim, actor)


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
        else:
            _lock_if_full(scrim, actor)
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
            "scrim", "team", "paid_by"
        )
        for row in rows:
            scrim = row.scrim
            if now() >= starts_at(scrim.date, scrim.session):
                continue
            scrim = _locked(scrim)
            held_place = row.status in HOLDS_PLACE
            if _drop(row, A.SUSPENDED_OUT, actor, why="Team suspended."):
                _changed(scrim)
            if held_place:
                _fill(scrim, actor)
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
