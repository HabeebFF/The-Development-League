import json

from django.core.management.base import BaseCommand

from apps.maps import bundled
from apps.maps.models import Map


class Command(BaseCommand):
    help = (
        "Write each calibrated map's points to default_images/<slug>.json, so the "
        "calibration ships with the bundled image. Only valid if the map still uses it."
    )

    def add_arguments(self, parser):
        parser.add_argument("slugs", nargs="*", help="Only these maps (default: all)")

    def handle(self, *args, slugs, **options):
        maps = Map.objects.exclude(transform=None)
        if slugs:
            maps = maps.filter(slug__in=slugs)
        for map_ in maps:
            points = [
                {
                    "label": p.label,
                    "world_x": p.world_x,
                    "world_z": p.world_z,
                    "pixel_x": p.pixel_x,
                    "pixel_y": p.pixel_y,
                }
                for p in map_.calibration_points.order_by("pk")
            ]
            path = bundled.DEFAULT_IMAGES_DIR / f"{map_.slug}.json"
            path.write_text(
                json.dumps({"source": "", "calibration_points": points}, indent=2) + "\n"
            )
            self.stdout.write(f"{map_.slug}: {len(points)} points -> {path.name}")
