"""Team rotations: where each team was at each checkpoint of a match (world x, z)."""

from django.conf import settings
from django.db import models

from common.models import TimeStampedModel

MAX_ZONES = 8


class Checkpoint(models.TextChoices):
    DROP = "DROP", "Drop"
    ZONE_1 = "ZONE_1", "Zone 1"
    ZONE_2 = "ZONE_2", "Zone 2"
    ZONE_3 = "ZONE_3", "Zone 3"
    ZONE_4 = "ZONE_4", "Zone 4"
    ZONE_5 = "ZONE_5", "Zone 5"
    ZONE_6 = "ZONE_6", "Zone 6"
    ZONE_7 = "ZONE_7", "Zone 7"
    ZONE_8 = "ZONE_8", "Zone 8"
    FINAL = "FINAL", "Final position"
    ELIMINATED = "ELIMINATED", "Eliminated"
    EXTRA = "EXTRA", "Extra point"


# Checkpoints a rotation has at most once (EXTRA can repeat).
SINGLE_CHECKPOINTS = {c for c in Checkpoint.values if c != Checkpoint.EXTRA}


class TeamRotation(TimeStampedModel):
    class Status(models.TextChoices):
        AUTO = "AUTO", "Auto draft"
        DRAFT = "DRAFT", "Edited by staff"
        CONFIRMED = "CONFIRMED", "Confirmed"

    match = models.ForeignKey("league.Match", on_delete=models.CASCADE, related_name="rotations")
    team = models.ForeignKey("league.Team", on_delete=models.CASCADE, related_name="rotations")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.AUTO)
    plotted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["match", "team__name"]
        unique_together = [("match", "team")]

    def __str__(self) -> str:
        return f"{self.match}: {self.team} ({self.status})"


class RotationPoint(models.Model):
    class Source(models.TextChoices):
        MANUAL = "MANUAL", "Plotted by staff"
        AUTO = "AUTO", "Auto from match events"

    rotation = models.ForeignKey(TeamRotation, on_delete=models.CASCADE, related_name="points")
    checkpoint = models.CharField(max_length=12, choices=Checkpoint.choices)
    order = models.PositiveSmallIntegerField(default=0)
    x = models.FloatField()
    z = models.FloatField()
    game_time_s = models.FloatField(null=True, blank=True)
    area = models.ForeignKey(
        "maps.MapArea", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.MANUAL)
    evidence = models.JSONField(
        default=dict, blank=True, help_text='Auto points: what they came from, e.g. {"kills": 2}'
    )
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["rotation", "order", "pk"]

    def __str__(self) -> str:
        return f"{self.rotation}: {self.checkpoint}"
