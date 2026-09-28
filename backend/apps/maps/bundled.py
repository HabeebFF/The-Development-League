"""Map images (and their calibration) that ship with the site.

Put ``<slug>.png`` (or ``.jpg`` / ``.webp``) in ``default_images/`` and every map without
an image gets it after ``migrate``, so nobody has to upload one. An optional
``<slug>.json`` next to it carries calibration points clicked once on that image::

    {"source": "where the image came from",
     "calibration_points": [{"label": "...", "world_x": 0, "world_z": 0,
                             "pixel_x": 0, "pixel_y": 0}, ...]}

A map that already has an image is left alone unless ``force`` is set, so an image the
Super Admin uploaded is never replaced behind their back.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from django.core.files import File
from django.db import transaction

from .models import CalibrationPoint, Map

logger = logging.getLogger(__name__)

DEFAULT_IMAGES_DIR = Path(__file__).resolve().parent / "default_images"
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


@dataclass
class Bundled:
    image: Path
    source: str = ""
    calibration_points: list[dict] = field(default_factory=list)


def find(slug: str, directory: Path | None = None) -> Bundled | None:
    """The bundled image (and calibration) for a map slug, if there is one."""
    directory = directory or DEFAULT_IMAGES_DIR
    image = next(
        (directory / f"{slug}{s}" for s in IMAGE_SUFFIXES if (directory / f"{slug}{s}").is_file()),
        None,
    )
    if image is None:
        return None
    bundled = Bundled(image=image)
    meta = directory / f"{slug}.json"
    if meta.is_file():
        data = json.loads(meta.read_text())
        bundled.source = data.get("source", "")
        bundled.calibration_points = data.get("calibration_points", [])
    return bundled


def install(map_: Map, *, force: bool = False, directory: Path | None = None) -> bool:
    """Give ``map_`` its bundled image and calibration. Returns True if it changed."""
    bundled = find(map_.slug, directory)
    if bundled is None or (map_.image and not force):
        return False
    with transaction.atomic():
        with bundled.image.open("rb") as fh:
            # Saving runs Pillow, which fills image_width / image_height.
            map_.image.save(f"{map_.slug}{bundled.image.suffix}", File(fh), save=True)
        # Old clicks were on another image; the bundled ones match this image.
        map_.calibration_points.all().delete()
        CalibrationPoint.objects.bulk_create(
            CalibrationPoint(
                map=map_,
                label=p.get("label", "")[:80],
                world_x=p["world_x"],
                world_z=p["world_z"],
                pixel_x=p["pixel_x"],
                pixel_y=p["pixel_y"],
            )
            for p in bundled.calibration_points
        )
        map_.recalibrate()
    return True


def install_all(*, force: bool = False, slugs: list[str] | None = None) -> list[str]:
    """Install bundled images on every map (or the given slugs). Returns changed slugs."""
    maps = Map.objects.all()
    if slugs:
        maps = maps.filter(slug__in=slugs)
    return [m.slug for m in maps if install(m, force=force)]


def install_missing(**kwargs) -> None:
    """post_migrate hook: fill in maps that have no image yet. Never breaks migrate."""
    try:
        changed = install_all()
    except Exception:  # storage down, bad file: log it, the site still works
        logger.exception("Could not install the bundled map images")
        return
    if changed:
        logger.info("Installed bundled map images: %s", ", ".join(changed))
