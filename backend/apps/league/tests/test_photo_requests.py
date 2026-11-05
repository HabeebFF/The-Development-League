"""Players asking to change their own card photo; staff approve or reject it."""

import io
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.league.models import PhotoRequest, Player

pytestmark = pytest.mark.django_db


def picture(name="me.png", fmt="PNG", colour=(200, 50, 50)) -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), colour).save(buf, fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")


def client_for(user: User) -> APIClient:
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def player_user():
    user = User.objects.create_user(email="p@tdl.test")
    Player.objects.create(
        game_uid=123,
        current_name_raw="VT ACE",
        display_name="VT ACE",
        search_name="vt ace",
        user=user,
    )
    return user


@pytest.fixture
def staff():
    return client_for(User.objects.create_user(email="s@tdl.test", is_staff=True))


@pytest.fixture(autouse=True)
def no_cutout():
    with mock.patch("apps.league.tasks.photo_cutout_task.delay") as delay:
        yield delay


def test_unlinked_account_sees_no_player_and_cannot_send():
    c = client_for(User.objects.create_user(email="fan@tdl.test"))
    assert c.get("/api/v1/me/card").json()["player"] is None
    resp = c.post("/api/v1/me/card/photo", {"photo": picture()}, format="multipart")
    assert resp.status_code == 400
    assert PhotoRequest.objects.count() == 0


def test_signed_out_is_refused():
    assert APIClient().get("/api/v1/me/card").status_code in (401, 403)
    assert APIClient().post("/api/v1/me/card/photo").status_code in (401, 403)


def test_player_sends_photo_and_it_waits_privately(player_user):
    c = client_for(player_user)
    resp = c.post("/api/v1/me/card/photo", {"photo": picture()}, format="multipart")
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["status"] == "PENDING"
    req = PhotoRequest.objects.get()
    assert req.photo.name.startswith("photo-requests/")
    # The card itself is untouched until staff approve.
    assert not Player.objects.get().photo
    mine = c.get("/api/v1/me/card").json()
    assert mine["player"]["name"] == "VT ACE"
    assert mine["player"]["photo"] is None
    assert mine["request"]["status"] == "PENDING"
    # The player can see their own picture; another account can't.
    assert c.get(body["image"]).status_code == 200
    other = client_for(User.objects.create_user(email="o@tdl.test"))
    assert other.get(body["image"]).status_code == 404


def test_bad_file_is_refused(player_user):
    c = client_for(player_user)
    junk = SimpleUploadedFile("x.png", b"not a picture", content_type="image/png")
    resp = c.post("/api/v1/me/card/photo", {"photo": junk}, format="multipart")
    assert resp.status_code == 400
    assert "photo" in resp.json()
    gif = c.post("/api/v1/me/card/photo", {"photo": picture("a.gif", "GIF")}, format="multipart")
    assert gif.status_code == 400


def test_new_photo_replaces_one_waiting_and_can_be_withdrawn(player_user):
    c = client_for(player_user)
    c.post("/api/v1/me/card/photo", {"photo": picture()}, format="multipart")
    c.post("/api/v1/me/card/photo", {"photo": picture(colour=(0, 0, 0))}, format="multipart")
    assert PhotoRequest.objects.filter(status="PENDING").count() == 1
    assert PhotoRequest.objects.filter(status="WITHDRAWN").count() == 1
    assert c.delete("/api/v1/me/card/photo").status_code == 204
    assert not PhotoRequest.objects.filter(status="PENDING").exists()
    assert c.delete("/api/v1/me/card/photo").status_code == 404


def test_staff_approve_puts_photo_on_card(
    player_user, staff, no_cutout, django_capture_on_commit_callbacks
):
    client_for(player_user).post("/api/v1/me/card/photo", {"photo": picture()}, format="multipart")
    listed = staff.get("/api/v1/admin/photo-requests").json()
    assert listed["pending"] == 1
    row = listed["results"][0]
    assert row["player"]["name"] == "VT ACE"
    assert row["requested_by"] == "p@tdl.test"
    assert staff.get(row["image"]).status_code == 200

    with django_capture_on_commit_callbacks(execute=True):
        resp = staff.post(f"/api/v1/admin/photo-requests/{row['id']}/approve")
    assert resp.status_code == 200, resp.content
    assert resp.json()["status"] == "APPROVED"
    player = Player.objects.get()
    assert player.photo.name.startswith("players/photos/")
    assert not player.photo_cutout
    no_cutout.assert_called_once_with(player.pk)
    req = PhotoRequest.objects.get()
    assert not req.photo  # the private copy is gone
    assert req.reviewed_by.email == "s@tdl.test"
    # Approving twice is refused.
    assert staff.post(f"/api/v1/admin/photo-requests/{row['id']}/approve").status_code == 400
    assert staff.get("/api/v1/admin/photo-requests").json()["pending"] == 0


def test_staff_reject_keeps_old_photo_and_tells_player(player_user, staff, no_cutout):
    c = client_for(player_user)
    c.post("/api/v1/me/card/photo", {"photo": picture()}, format="multipart")
    req = PhotoRequest.objects.get()
    resp = staff.post(
        f"/api/v1/admin/photo-requests/{req.pk}/reject", {"reason": "Face not clear"}, format="json"
    )
    assert resp.status_code == 200
    assert not Player.objects.get().photo
    no_cutout.assert_not_called()
    mine = c.get("/api/v1/me/card").json()["request"]
    assert mine["status"] == "REJECTED"
    assert mine["reason"] == "Face not clear"
    assert mine["image"] is None


def test_only_staff_review(player_user):
    c = client_for(player_user)
    c.post("/api/v1/me/card/photo", {"photo": picture()}, format="multipart")
    req = PhotoRequest.objects.get()
    assert c.get("/api/v1/admin/photo-requests").status_code == 403
    assert c.post(f"/api/v1/admin/photo-requests/{req.pk}/approve").status_code == 403
    assert not Player.objects.get().photo
