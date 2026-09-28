"""Images (and calibration) bundled with the site."""

import json

import pytest
from django.core.management import call_command
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.maps import bundled
from apps.maps.models import CalibrationPoint, Map

pytestmark = pytest.mark.django_db

POINTS = [
    {"label": "west", "world_x": -500, "world_z": -400, "pixel_x": 85.3, "pixel_y": 853.3},
    {"label": "east", "world_x": 450, "world_z": 380, "pixel_x": 896.0, "pixel_y": 188.0},
]


@pytest.fixture
def images(tmp_path, monkeypatch):
    Image.new("RGB", (1024, 768), "navy").save(tmp_path / "purgatory.png")
    (tmp_path / "purgatory.json").write_text(
        json.dumps({"source": "test", "calibration_points": POINTS})
    )
    Image.new("RGB", (640, 640), "green").save(tmp_path / "bermuda.webp")
    monkeypatch.setattr(bundled, "DEFAULT_IMAGES_DIR", tmp_path)
    return tmp_path


def test_maps_without_an_image_get_the_bundled_one(images):
    assert sorted(bundled.install_all()) == ["bermuda", "purgatory"]
    purgatory = Map.objects.get(slug="purgatory")
    assert (purgatory.image_width, purgatory.image_height) == (1024, 768)
    assert purgatory.calibration_points.count() == 2
    assert purgatory.transform is not None and purgatory.calibration_error < 1e-6
    bermuda = Map.objects.get(slug="bermuda")
    assert (bermuda.image_width, bermuda.image_height) == (640, 640)
    assert bermuda.transform is None
    assert not Map.objects.get(slug="kalahari").image


def test_an_uploaded_image_is_kept_unless_forced(images):
    bundled.install_all()
    purgatory = Map.objects.get(slug="purgatory")
    CalibrationPoint.objects.create(
        map=purgatory, world_x=0, world_z=0, pixel_x=1, pixel_y=1, label="mine"
    )
    assert bundled.install_all() == []
    assert purgatory.calibration_points.count() == 3

    call_command("load_map_images", "purgatory", "--force")
    assert list(purgatory.calibration_points.values_list("label", flat=True)) == [
        "west",
        "east",
    ]


def test_super_admin_can_put_the_built_in_image_back(images):
    client = APIClient()
    client.force_authenticate(User.objects.create_superuser(email="b@tdl.test", password="x"))
    listed = {m["slug"]: m for m in client.get("/api/v1/admin/maps").json()["results"]}
    assert listed["purgatory"]["has_default_image"] is True
    assert listed["kalahari"]["has_default_image"] is False

    res = client.post("/api/v1/admin/maps/purgatory/use-default-image")
    assert res.status_code == 200
    assert res.json()["image_width"] == 1024 and res.json()["is_calibrated"] is True
    assert client.post("/api/v1/admin/maps/kalahari/use-default-image").status_code == 404

    staff = APIClient()
    staff.force_authenticate(User.objects.create_user(email="s@tdl.test", is_staff=True))
    assert staff.post("/api/v1/admin/maps/purgatory/use-default-image").status_code == 403


def test_migrate_hook_never_raises(monkeypatch):
    def boom(**kwargs):
        raise OSError("storage down")

    monkeypatch.setattr(bundled, "install_all", boom)
    bundled.install_missing()
