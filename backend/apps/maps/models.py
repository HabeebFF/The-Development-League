"""Game maps, their calibration (world <-> image) and named areas.

Positions everywhere are stored in game world coordinates (x, z); pixels are only
computed for drawing, so re-calibrating a map never breaks old data.
"""

from django.db import models
from django.utils import timezone

from common.models import TimeStampedModel

from . import calibration


class Map(TimeStampedModel):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    game_map_id = models.IntegerField(
        unique=True, null=True, blank=True, help_text="MapID / map_id as written in the logs"
    )
    image = models.ImageField(
        upload_to="maps/", blank=True, width_field="image_width", height_field="image_height"
    )
    image_width = models.PositiveIntegerField(null=True, blank=True)
    image_height = models.PositiveIntegerField(null=True, blank=True)
    transform = models.JSONField(
        null=True, blank=True, help_text="Affine transform world (x, z) -> image pixels"
    )
    calibration_error = models.FloatField(
        null=True, blank=True, help_text="RMS pixel error of the calibration points"
    )
    calibrated_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def recalibrate(self) -> calibration.Fit | None:
        """Refit from the calibration points and save. Returns None below 2 points."""
        points = [
            calibration.Point(p.world_x, p.world_z, p.pixel_x, p.pixel_y)
            for p in self.calibration_points.order_by("pk")
        ]
        try:
            result = calibration.fit(points)
        except calibration.CalibrationError:
            result = None
        self.transform = result.transform.as_dict() if result else None
        self.calibration_error = round(result.rms_error, 3) if result else None
        self.calibrated_at = timezone.now() if result else None
        self.save(update_fields=["transform", "calibration_error", "calibrated_at", "updated_at"])
        return result


class CalibrationPoint(TimeStampedModel):
    """A spot whose world position is known (e.g. from a kill) clicked on the image."""

    map = models.ForeignKey(Map, on_delete=models.CASCADE, related_name="calibration_points")
    label = models.CharField(max_length=80, blank=True)
    world_x = models.FloatField()
    world_z = models.FloatField()
    pixel_x = models.FloatField()
    pixel_y = models.FloatField()

    class Meta:
        ordering = ["map", "pk"]

    def __str__(self) -> str:
        return f"{self.map}: {self.label or self.pk}"


class MapAreaQuerySet(models.QuerySet):
    def confirmed(self):
        return self.filter(status=MapArea.Status.CONFIRMED)


class MapArea(TimeStampedModel):
    """A named place ("Clock Tower") as a polygon in world coordinates.

    A SUGGESTED area was outlined from guides, not by staff: it is only shown to staff
    until one of them confirms it, and nothing is labelled with it before then.
    """

    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Confirmed"
        SUGGESTED = "SUGGESTED", "Suggested"

    map = models.ForeignKey(Map, on_delete=models.CASCADE, related_name="areas")
    name = models.CharField(max_length=80)
    polygon = models.JSONField(help_text="[[x, z], ...] world coordinates, at least 3")
    centre_x = models.FloatField()
    centre_z = models.FloatField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CONFIRMED)
    note = models.TextField(blank=True, help_text="Where a suggested outline came from")

    objects = MapAreaQuerySet.as_manager()

    class Meta:
        ordering = ["map", "name"]
        unique_together = [("map", "name")]

    def __str__(self) -> str:
        return f"{self.map}: {self.name}"

    def save(self, *args, **kwargs):
        self.centre_x, self.centre_z = calibration.polygon_centre(self.polygon)
        super().save(*args, **kwargs)

    def contains(self, x: float, z: float) -> bool:
        return calibration.point_in_polygon(x, z, self.polygon)

    @classmethod
    def find(cls, map_id: int | None, x: float, z: float, areas=None) -> "MapArea | None":
        """The area containing (x, z); the smallest one when areas overlap."""
        if map_id is None and areas is None:
            return None
        candidates = areas if areas is not None else cls.objects.confirmed().filter(map_id=map_id)
        hits = [a for a in candidates if a.contains(x, z)]
        return min(hits, key=lambda a: _polygon_area(a.polygon)) if hits else None


def _polygon_area(polygon: list[list[float]]) -> float:
    n = len(polygon)
    return abs(
        sum(
            polygon[i][0] * polygon[(i + 1) % n][1] - polygon[(i + 1) % n][0] * polygon[i][1]
            for i in range(n)
        )
        / 2
    )
