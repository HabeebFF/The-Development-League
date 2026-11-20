"""Scrim registration: teams sign up for a night's 8PM and 10PM sessions.

Plan: /mnt/project-files/design/SCRIM-REGISTRATION.md (approved 2026-11-13). The rules live
in ``services.py``; these are only the records.
"""

import datetime as dt

from django.conf import settings
from django.db import models


def scrim_weekdays() -> list[int]:
    return [0, 1, 3, 4]  # Monday, Tuesday, Thursday, Friday


def close_times() -> dict[str, str]:
    return {"8PM": "18:00", "10PM": "20:00"}


class ScrimSettings(models.Model):
    """When scrims happen and how sign-up works (one row)."""

    weekdays = models.JSONField(default=scrim_weekdays, help_text="Scrim days: 0 = Monday ... 6")
    skip_dates = models.JSONField(default=list, blank=True, help_text="Nights off, YYYY-MM-DD")
    opens_at = models.TimeField(default=dt.time(20), help_text="Sign-up opens, Lagos time")
    opens_days_before = models.PositiveSmallIntegerField(
        default=1, help_text="Sign-up opens this many days before the scrim night (0 = that day)"
    )
    fee = models.PositiveIntegerField(
        default=500, help_text="DC a team pays per session to sign up or confirm (0 = free)"
    )
    closes_at = models.JSONField(
        default=close_times, help_text='Sign-up closes per session, e.g. {"8PM": "18:00"}'
    )
    max_teams = models.PositiveSmallIntegerField(default=12, help_text="Places per session")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "scrim settings"

    @classmethod
    def get(cls) -> "ScrimSettings":
        return cls.objects.get_or_create(pk=1)[0]


class ScrimSession(models.Model):
    """One session of one night, e.g. Monday 2026-11-16 8PM. Made when first needed."""

    class Session(models.TextChoices):
        PM8 = "8PM", "8PM"
        PM10 = "10PM", "10PM"

    date = models.DateField()
    session = models.CharField(max_length=4, choices=Session.choices)
    max_teams = models.PositiveSmallIntegerField(help_text="Places; staff can change it")
    locked_at = models.DateTimeField(
        null=True, blank=True, help_text="Filled up: sign-up locked and predictions opened"
    )
    wrapped_at = models.DateTimeField(
        null=True, blank=True, help_text="Sign-up closed: invites dropped, waitlist refunded"
    )
    maps = models.JSONField(
        default=list, blank=True, help_text="Map ids in match order, drawn when sign-up opens"
    )
    maps_drawn_at = models.DateTimeField(null=True, blank=True)
    maps_set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Staff who last changed the maps (empty: the site drew them)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "session"]
        constraints = [
            models.UniqueConstraint(fields=["date", "session"], name="unique_scrim_session"),
        ]

    def __str__(self) -> str:
        return f"{self.date} {self.session}"


class Registration(models.Model):
    """A team's place in a session: playing, invited by staff (place held until the team
    confirms), or on the waitlist (in sign-up order)."""

    class Status(models.TextChoices):
        REGISTERED = "REGISTERED", "Registered"
        INVITED = "INVITED", "Invited"
        WAITLIST = "WAITLIST", "Waitlist"

    scrim = models.ForeignKey(ScrimSession, on_delete=models.CASCADE, related_name="registrations")
    team = models.ForeignKey("league.Team", on_delete=models.CASCADE, related_name="scrim_entries")
    status = models.CharField(max_length=10, choices=Status.choices)
    by_staff = models.BooleanField(default=False, help_text="Added by staff, not the team")
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    fee_paid = models.PositiveIntegerField(default=0, help_text="DC paid to sign up")
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scrim", "created_at", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["scrim", "team"], name="unique_scrim_registration"),
        ]

    def __str__(self) -> str:
        return f"{self.team} in {self.scrim} ({self.status})"


class Suspension(models.Model):
    """A team can't register while a suspension is open: not ended, and its end date (if any)
    not passed. Kept after it ends, as history."""

    team = models.ForeignKey("league.Team", on_delete=models.CASCADE, related_name="suspensions")
    reason = models.CharField(max_length=300, blank=True, help_text="Shown to the team")
    until = models.DateField(null=True, blank=True, help_text="Last day; empty = until lifted")
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at", "-pk"]

    def __str__(self) -> str:
        return f"{self.team} suspended {self.started_at:%Y-%m-%d}"


class ScrimLog(models.Model):
    """Everything that changed who plays: sign-ups, withdrawals, staff changes, suspensions."""

    class Action(models.TextChoices):
        REGISTERED = "REGISTERED", "Registered"
        WAITLISTED = "WAITLISTED", "Joined the waitlist"
        WITHDREW = "WITHDREW", "Withdrew"
        MOVED_UP = "MOVED_UP", "Moved up from the waitlist"
        STAFF_ADDED = "STAFF_ADDED", "Added by staff"
        STAFF_REMOVED = "STAFF_REMOVED", "Removed by staff"
        SUSPENDED = "SUSPENDED", "Suspended"
        UNSUSPENDED = "UNSUSPENDED", "Unsuspended"
        SUSPENDED_OUT = "SUSPENDED_OUT", "Removed: suspended"
        INVITED = "INVITED", "Invited by staff"
        CONFIRMED = "CONFIRMED", "Confirmed the invite"
        DECLINED = "DECLINED", "Declined the invite"
        INVITE_EXPIRED = "INVITE_EXPIRED", "Invite not confirmed in time"
        FILLED = "FILLED", "Session full: sign-up locked"
        REFUNDED = "REFUNDED", "Sign-up DC refunded"

    scrim = models.ForeignKey(
        ScrimSession, on_delete=models.CASCADE, null=True, blank=True, related_name="log"
    )
    team = models.ForeignKey("league.Team", on_delete=models.CASCADE, related_name="+")
    action = models.CharField(max_length=14, choices=Action.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    note = models.CharField(max_length=300, blank=True)
    at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-at", "-pk"]

    def __str__(self) -> str:
        return f"{self.team} {self.action}"
