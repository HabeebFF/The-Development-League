"""Game maps. Calibration points and named areas arrive in step (e)."""

from django.db import models

from common.models import TimeStampedModel


class Map(TimeStampedModel):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    game_map_id = models.IntegerField(
        unique=True, null=True, blank=True, help_text="MapID / map_id as written in the logs"
    )
    image = models.FileField(upload_to="maps/", blank=True)
    image_width = models.PositiveIntegerField(null=True, blank=True)
    image_height = models.PositiveIntegerField(null=True, blank=True)
    transform = models.JSONField(
        null=True, blank=True, help_text="Affine transform world (x, z) -> image pixels"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
