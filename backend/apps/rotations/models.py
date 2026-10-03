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
    path = models.JSONField(
        default=list,
        blank=True,
        help_text="The team's real route from the replay: pieces of [x, z] in world decimetres",
    )

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


class PlayerTrack(models.Model):
    """One player's path through a match, from the replay .bin, for the live replay.

    ``points`` holds one ``[x, z]`` (world decimetres) every ``step_s`` seconds from
    ``start_s``; ``null`` where the player was not in the feed (plane, dead, gaps).
    """

    match = models.ForeignKey("league.Match", on_delete=models.CASCADE, related_name="tracks")
    entity_id = models.BigIntegerField()
    player = models.ForeignKey(
        "league.Player", null=True, blank=True, on_delete=models.SET_NULL, related_name="tracks"
    )
    team = models.ForeignKey(
        "league.Team", null=True, blank=True, on_delete=models.SET_NULL, related_name="tracks"
    )
    start_s = models.FloatField()
    step_s = models.FloatField()
    points = models.JSONField()

    class Meta:
        ordering = ["match", "team", "entity_id"]
        unique_together = [("match", "entity_id")]

    def __str__(self) -> str:
        return f"{self.match}: {self.player or self.entity_id}"


class ReplayObject(models.Model):
    """A UAV, Bolt Maker lightning zone or Dinoculars scan in the live replay (from the
    replay .bin).

    ``points`` is ``[[t, x_dm, z_dm], ...]``: a UAV's flight path, or a Bolt Maker's
    strikes (one a second); empty for a scan. ``x``/``z`` is where it starts (a Bolt
    Maker's centre, the spot a Dinoculars scan looked at).
    """

    class Kind(models.TextChoices):
        PLAYER_UAV = "PLAYER_UAV", "Player UAV"
        GENERAL_UAV = "GENERAL_UAV", "General UAV"
        BOLT_MAKER = "BOLT_MAKER", "Bolt Maker"
        DINOCULARS = "DINOCULARS", "Dinoculars"

    match = models.ForeignKey(
        "league.Match", on_delete=models.CASCADE, related_name="replay_objects"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    owner_entity = models.BigIntegerField(null=True, blank=True)
    player = models.ForeignKey(
        "league.Player", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    team = models.ForeignKey(
        "league.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    start_s = models.FloatField()
    end_s = models.FloatField()
    x = models.FloatField()
    z = models.FloatField()
    radius_m = models.FloatField(
        null=True,
        blank=True,
        help_text="Metres a UAV scans around itself, or a Bolt Maker zone's radius",
    )
    points = models.JSONField(default=list)

    class Meta:
        ordering = ["match", "start_s", "id"]

    def __str__(self) -> str:
        return f"{self.match}: {self.kind} @ {self.start_s:.0f}s"
