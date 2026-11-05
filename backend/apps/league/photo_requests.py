"""Players changing the photo on their own card.

A signed-in player whose account is linked to their game UID sends a new photo from
"My card". It waits, private, until staff approve it; then it becomes the card photo and the
background cut-out is made as for a photo staff upload. Names are not editable here: they
keep coming from the match logs.
"""

from __future__ import annotations

import os

from django.core.files.base import ContentFile
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsStaff

from .models import PhotoRequest, Player
from .serializers import check_photo

REASON_MAX = 200


def _image_url(req: PhotoRequest) -> str | None:
    return f"/api/v1/photo-requests/{req.pk}/image" if req.photo else None


def request_data(req: PhotoRequest, staff: bool = False) -> dict:
    player = req.player
    data = {
        "id": req.pk,
        "status": req.status,
        "image": _image_url(req),
        "reason": req.reason,
        "created_at": req.created_at,
        "reviewed_at": req.reviewed_at,
    }
    if staff:
        team = player.current_team
        data["player"] = {
            "id": player.pk,
            "name": player.display_name,
            "game_uid": str(player.game_uid),
            "team": (team.tag or team.name) if team else None,
            "photo": player.photo_cutout.url
            if player.photo_cutout
            else (player.photo.url if player.photo else None),
        }
        data["requested_by"] = req.requested_by.email if req.requested_by else None
        data["reviewed_by"] = req.reviewed_by.email if req.reviewed_by else None
    return data


def _my_player(request) -> Player | None:
    return Player.objects.select_related("current_team").filter(user=request.user).first()


class MyCardView(APIView):
    """The signed-in player's own card, current photo and latest photo request.

    GET: ``{"player": null}`` when the account isn't linked to a game UID yet.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.models import PlayerClaim
        from apps.results.models import PlayerCard

        from .views import _card

        player = _my_player(request)
        if player is None:
            claim = request.user.player_claims.filter(status=PlayerClaim.Status.PENDING).first()
            return Response(
                {"player": None, "pending_uid_claim": str(claim.game_uid) if claim else None}
            )
        card = (
            PlayerCard.objects.filter(player=player)
            .select_related("player", "team")
            .order_by("-week")
            .first()
        )
        latest = player.photo_requests.first()
        team = player.current_team
        return Response(
            {
                "player": {
                    "id": player.pk,
                    "name": player.display_name,
                    "game_uid": str(player.game_uid),
                    "team": {"name": team.name, "tag": team.tag} if team else None,
                    "photo": player.photo_cutout.url
                    if player.photo_cutout
                    else (player.photo.url if player.photo else None),
                    "card_hidden": player.hide_card,
                },
                "card": _card(card, request) if card else None,
                "request": request_data(latest) if latest else None,
            }
        )


class MyPhotoView(APIView):
    """POST a new photo (multipart ``photo``) for staff to approve; it replaces one still
    waiting. DELETE takes back the one waiting."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        player = _my_player(request)
        if player is None:
            raise ValidationError({"detail": "Link your game UID to your account first."})
        upload = request.FILES.get("photo")
        if not upload:
            raise ValidationError({"photo": "Choose a picture."})
        try:
            check_photo(upload)
        except ValidationError as exc:
            raise ValidationError({"photo": exc.detail}) from exc
        with transaction.atomic():
            _withdraw(player)
            req = PhotoRequest(player=player, requested_by=request.user)
            ext = os.path.splitext(upload.name)[1].lower()[:5] or ".jpg"
            req.photo.save(f"player-{player.pk}{ext}", upload, save=False)
            req.save()
        return Response(request_data(req), status=status.HTTP_201_CREATED)

    def delete(self, request):
        player = _my_player(request)
        if player is None or not _withdraw(player):
            raise Http404
        return Response(status=status.HTTP_204_NO_CONTENT)


def _withdraw(player: Player) -> bool:
    """Take back the player's request still waiting, if any (its picture goes too)."""
    found = False
    for req in PhotoRequest.objects.select_for_update().filter(
        player=player, status=PhotoRequest.Status.PENDING
    ):
        req.photo.delete(save=False)
        req.status = PhotoRequest.Status.WITHDRAWN
        req.save(update_fields=["photo", "status"])
        found = True
    return found


class PhotoRequestImageView(APIView):
    """The picture in a request: only for the player who sent it, and for staff."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        req = get_object_or_404(PhotoRequest.objects.select_related("player"), pk=pk)
        if not (request.user.is_league_staff or req.player.user_id == request.user.pk):
            raise Http404
        if not req.photo:
            raise Http404
        resp = FileResponse(req.photo.open("rb"))
        resp["Cache-Control"] = "private, max-age=300"
        return resp


class PhotoRequestAdminView(APIView):
    """Staff: GET the requests (``?status=PENDING`` by default, ``all`` for every one)."""

    permission_classes = [IsStaff]

    def get(self, request):
        wanted = request.query_params.get("status", PhotoRequest.Status.PENDING)
        qs = PhotoRequest.objects.select_related(
            "player__current_team", "requested_by", "reviewed_by"
        )
        if wanted != "all":
            qs = qs.filter(status=wanted)
        rows = list(qs[:100])
        pending = PhotoRequest.objects.filter(status=PhotoRequest.Status.PENDING).count()
        return Response(
            {"pending": pending, "results": [request_data(r, staff=True) for r in rows]}
        )


class PhotoRequestReviewView(APIView):
    """Staff: POST ``approve`` puts the photo on the card (and makes the cut-out); ``reject``
    with an optional ``{"reason": ...}`` the player will see."""

    permission_classes = [IsStaff]

    def post(self, request, pk: int, verdict: str):
        if verdict not in ("approve", "reject"):
            raise Http404
        with transaction.atomic():
            req = get_object_or_404(
                PhotoRequest.objects.select_for_update().select_related("player"), pk=pk
            )
            if req.status != PhotoRequest.Status.PENDING:
                raise ValidationError({"detail": "This request was already dealt with."})
            if verdict == "approve":
                _approve(req)
            else:
                req.reason = str(request.data.get("reason") or "").strip()[:REASON_MAX]
                req.photo.delete(save=False)
                req.status = PhotoRequest.Status.REJECTED
            req.reviewed_by = request.user
            req.reviewed_at = timezone.now()
            req.save()
        req.refresh_from_db()
        return Response(request_data(req, staff=True))


def _approve(req: PhotoRequest) -> None:
    """Move the picture onto the player's card, as if staff had uploaded it."""
    from .tasks import photo_cutout_task

    player = Player.objects.select_for_update().get(pk=req.player_id)
    with req.photo.open("rb") as f:
        content = f.read()
    name = os.path.basename(req.photo.name)
    player.photo.delete(save=False)
    player.photo_cutout.delete(save=False)
    player.photo.save(name, ContentFile(content), save=False)
    player.photo_cutout = ""
    player.save(update_fields=["photo", "photo_cutout", "updated_at"])
    req.photo.delete(save=False)
    req.status = PhotoRequest.Status.APPROVED
    req.player = player
    transaction.on_commit(lambda: photo_cutout_task.delay(player.pk))
