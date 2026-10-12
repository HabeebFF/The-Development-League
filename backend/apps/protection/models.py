"""Protection Points (PP): staff set tasks for a scrim day, the site checks each team.

A period (usually two weeks) starts everyone on 0 plus any starting PP staff enter. Each task
gives ``pp_done`` when a team does it and ``pp_not_done`` when it doesn't; most tasks are
checked from the uploaded logs (see ``apps.protection.rules``), the rest staff tick by hand.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from common.models import TimeStampedModel


class Period(TimeStampedModel):
    name = models.CharField(max_length=80)
    starts_on = models.DateField()
    ends_on = models.DateField()

    class Meta:
        ordering = ["-starts_on", "-id"]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        if self.ends_on and self.starts_on and self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": "Ends before it starts."})


class Task(TimeStampedModel):
    class Rule(models.TextChoices):
        ZONE_ALIVE = "ZONE_ALIVE", "Full squad alive at a zone"
        BOOYAH = "BOOYAH", "Booyahs"
        DAY_POINTS = "DAY_POINTS", "Total points for the day"
        DAY_KILLS = "DAY_KILLS", "Kills for the day"
        PLACEMENT = "PLACEMENT", "Top placements"
        MANUAL = "MANUAL", "Staff tick it"

    period = models.ForeignKey(Period, on_delete=models.CASCADE, related_name="tasks")
    date = models.DateField(help_text="The scrim day it is checked on")
    match_days = models.ManyToManyField(
        "league.MatchDay",
        blank=True,
        related_name="+",
        help_text="Only these sessions; empty means every match played that date",
    )
    title = models.CharField(max_length=120)
    rule = models.CharField(max_length=12, choices=Rule.choices)
    params = models.JSONField(
        default=dict,
        blank=True,
        help_text='ZONE_ALIVE {"zone": 5, "min_matches": 4}; BOOYAH {"once": false}; '
        'DAY_POINTS/DAY_KILLS {"op": "lt"|"gte", "value": 45}; '
        'PLACEMENT {"top": 3, "min_matches": 2}',
    )
    pp_done = models.IntegerField(default=0)
    pp_not_done = models.IntegerField(default=0)
    is_published = models.BooleanField(
        default=True, help_text="Hidden tasks don't count and only staff see them"
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["date", "order", "id"]

    def __str__(self) -> str:
        return f"{self.date} {self.title}"


class TaskResult(TimeStampedModel):
    """How one team did on one task. Rebuilt from the logs; staff overrides are kept."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="results")
    team = models.ForeignKey("league.Team", on_delete=models.CASCADE, related_name="+")
    matches = models.JSONField(default=list, help_text="Match ids the team played for it")
    done = models.BooleanField(null=True, help_text="From the logs; empty until staff tick it")
    count = models.PositiveSmallIntegerField(default=0, help_text="Booyahs, for per-booyah PP")
    detail = models.CharField(max_length=160, blank=True)
    evidence = models.JSONField(default=list, blank=True, help_text="[{match, ok, note}]")
    override = models.BooleanField(null=True, help_text="Staff's done / not done")
    note = models.CharField(max_length=160, blank=True)
    pp = models.IntegerField(default=0)

    class Meta:
        ordering = ["task", "team__name"]
        constraints = [models.UniqueConstraint(fields=["task", "team"], name="one_pp_result")]

    @property
    def final(self) -> bool | None:
        return self.override if self.override is not None else self.done

    def score(self) -> int:
        done, task = self.final, self.task
        if done is None:
            return 0
        if not done:
            return task.pp_not_done
        if task.rule == Task.Rule.BOOYAH and not task.params.get("once"):
            return task.pp_done * max(self.count, 1)
        return task.pp_done


class Adjustment(TimeStampedModel):
    """Starting PP for a period, or a one-off change staff make (with a reason)."""

    class Kind(models.TextChoices):
        START = "START", "Starting PP"
        ADJUST = "ADJUST", "Adjustment"

    period = models.ForeignKey(Period, on_delete=models.CASCADE, related_name="adjustments")
    team = models.ForeignKey("league.Team", on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=6, choices=Kind.choices, default=Kind.ADJUST)
    pp = models.IntegerField()
    reason = models.CharField(max_length=160, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["period", "created_at"]

    def __str__(self) -> str:
        return f"{self.team} {self.pp:+d} ({self.reason or self.kind})"
