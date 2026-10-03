"""Calibration maths and the map admin API."""

import io
import math

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.testing import signed_in_client
from apps.maps.calibration import (
    CalibrationError,
    Point,
    Transform,
    fit,
    point_in_polygon,
    polygon_centre,
)
from apps.maps.models import Map, MapArea

# A made-up map: 1024 px image of a world from -600 to 600, image y pointing south.
TRUTH = Transform(a=1024 / 1200, b=0.0, c=512.0, d=0.0, e=-1024 / 1200, f=512.0)


def truth_point(x: float, z: float, jitter: tuple[float, float] = (0, 0)) -> Point:
    px, py = TRUTH.to_pixel(x, z)
    return Point(x, z, px + jitter[0], py + jitter[1])


def close(t: Transform, other: Transform, tol: float = 1e-6) -> bool:
    return all(math.isclose(getattr(t, k), getattr(other, k), abs_tol=tol) for k in "abcdef")


def test_two_points_fit_each_axis_and_flip():
    result = fit([truth_point(-500, -400), truth_point(450, 380)])
    assert close(result.transform, TRUTH)
    assert result.rms_error < 1e-6
    x, z = result.transform.to_world(*TRUTH.to_pixel(123.0, -45.0))
    assert math.isclose(x, 123.0, abs_tol=1e-6) and math.isclose(z, -45.0, abs_tol=1e-6)


def test_two_points_need_spread_on_both_axes():
    with pytest.raises(CalibrationError):
        fit([truth_point(-500, 100), truth_point(450, 100)])
    with pytest.raises(CalibrationError):
        fit([truth_point(0, 0)])


def test_three_points_fit_rotation():
    angle = math.radians(30)
    rotated = Transform(
        math.cos(angle), -math.sin(angle), 400, math.sin(angle), math.cos(angle), 300
    )
    points = []
    for x, z in [(-300, -200), (250, -150), (100, 320)]:
        px, py = rotated.to_pixel(x, z)
        points.append(Point(x, z, px, py))
    assert close(fit(points).transform, rotated, tol=1e-6)


def test_bad_click_shows_in_the_error():
    good = [truth_point(-500, -400), truth_point(450, 380), truth_point(-300, 350)]
    assert fit(good).rms_error < 1e-6
    bad = fit([*good, truth_point(200, -250, jitter=(40, -30))])
    assert bad.rms_error > 10
    assert max(bad.residuals) == bad.residuals[3]  # the bad click stands out


def test_collinear_points_are_rejected():
    with pytest.raises(CalibrationError):
        fit([truth_point(-100, -100), truth_point(0, 0), truth_point(100, 100)])


def test_polygons():
    square = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert point_in_polygon(5, 5, square) and not point_in_polygon(15, 5, square)
    assert polygon_centre(square) == (5.0, 5.0)
    assert polygon_centre([[0, 0], [0, 0], [0, 0]]) == (0.0, 0.0)


# -- API --------------------------------------------------------------------------------------


@pytest.fixture
def boss() -> APIClient:
    client = APIClient()
    client.force_authenticate(
        User.objects.create_user(email="boss@tdl.test", is_staff=True, is_superuser=True)
    )
    return client


def png(width: int, height: int) -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "black").save(buf, format="PNG")
    return SimpleUploadedFile("bermuda.png", buf.getvalue(), content_type="image/png")


@pytest.mark.django_db
def test_upload_image_and_calibrate(boss):
    resp = boss.patch("/api/v1/admin/maps/bermuda", {"image": png(1024, 1024)}, format="multipart")
    assert resp.status_code == 200, resp.content
    assert (resp.json()["image_width"], resp.json()["image_height"]) == (1024, 1024)
    assert resp.json()["is_calibrated"] is False

    url = "/api/v1/admin/maps/bermuda/calibration-points"
    p1, p2 = truth_point(-500, -400), truth_point(450, 380)
    for label, p in (("Clock tower", p1), ("Airport", p2)):
        resp = boss.post(
            url,
            {
                "label": label,
                "world_x": p.world_x,
                "world_z": p.world_z,
                "pixel_x": p.pixel_x,
                "pixel_y": p.pixel_y,
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
    state = boss.get(url).json()
    assert state["calibration_error"] == 0 and state["points"][0]["error_px"] == 0
    assert close(Transform.from_dict(state["transform"]), TRUTH)
    assert signed_in_client().get("/api/v1/maps/bermuda").json()["is_calibrated"] is True

    outside = boss.post(
        url, {"world_x": 0, "world_z": 0, "pixel_x": 2000, "pixel_y": 5}, format="json"
    )
    assert outside.status_code == 400

    # Replacing all points at once (the overlay tool), then deleting down to one point.
    points = [truth_point(-500, -400), truth_point(450, 380), truth_point(-300, 350)]
    resp = boss.put(
        url,
        {
            "points": [
                {
                    "world_x": p.world_x,
                    "world_z": p.world_z,
                    "pixel_x": p.pixel_x,
                    "pixel_y": p.pixel_y,
                }
                for p in points
            ]
        },
        format="json",
    )
    assert resp.status_code == 200 and len(resp.json()["points"]) == 3
    for point in resp.json()["points"][:2]:
        boss.delete(f"{url}/{point['id']}")
    assert Map.objects.get(slug="bermuda").transform is None

    # A new image clears the old clicks.
    boss.patch("/api/v1/admin/maps/bermuda", {"image": png(2048, 2048)}, format="multipart")
    assert boss.get(url).json()["points"] == []


@pytest.mark.django_db
def test_areas_and_permissions(boss):
    url = "/api/v1/admin/maps/purgatory/areas"
    resp = boss.post(
        url,
        {"name": "Brasilia", "polygon": [[0, 0], [100, 0], [100, 100], [0, 100]]},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert (resp.json()["centre_x"], resp.json()["centre_z"]) == (50.0, 50.0)
    assert (
        boss.post(
            url, {"name": "Brasilia", "polygon": [[0, 0], [1, 0], [0, 1]]}, format="json"
        ).status_code
        == 400
    )
    assert (
        boss.post(url, {"name": "Bad", "polygon": [[0, 0], [1, 0]]}, format="json").status_code
        == 400
    )
    assert (
        boss.post(
            url, {"name": "Bad", "polygon": [[0, "x"], [1, 0], [2, 2]]}, format="json"
        ).status_code
        == 400
    )
    assert MapArea.find(Map.objects.get(slug="purgatory").pk, 50, 50).name == "Brasilia"

    public = signed_in_client().get("/api/v1/maps/purgatory").json()
    assert public["areas"][0]["name"] == "Brasilia"

    # Staff draw areas (they are part of the coach's knowledge base); images and
    # calibration stay with the Super Admin. Players can do neither.
    staff = APIClient()
    staff.force_authenticate(User.objects.create_user(email="s@tdl.test", is_staff=True))
    assert staff.get(url).status_code == 200
    assert staff.get("/api/v1/admin/maps").status_code == 403
    assert staff.get("/api/v1/admin/maps/bermuda/calibration-points").status_code == 403
    player = APIClient()
    player.force_authenticate(User.objects.create_user(email="p@tdl.test"))
    assert player.get(url).status_code == 403
    assert APIClient().get("/api/v1/admin/maps/bermuda/calibration-points").status_code == 401
    assert boss.get("/api/v1/admin/maps/nowhere/areas").status_code == 404


@pytest.mark.django_db
def test_image_url_is_not_rewritten_to_the_api_host(boss):
    boss.patch("/api/v1/admin/maps/kalahari", {"image": png(64, 64)}, format="multipart")
    image = signed_in_client().get("/api/v1/maps/kalahari").json()["image"]
    assert image.startswith("/media/maps/")  # same origin as the website in development
