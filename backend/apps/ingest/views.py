"""Staff upload API.

Flow: create a batch -> ask which files the server already has (``known``) -> add the
rest (direct upload, or presign + PUT to S3 + register) -> files are read in the
background and a per-match preview appears on the batch -> confirm with a match day /
number per match -> matches are built in the background.
"""

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.league.models import Match
from common.permissions import IsStaff

from . import tasks
from .models import ParseRun, UploadBatch, UploadedFile
from .serializers import (
    ConfirmSerializer,
    KnownSerializer,
    ParseRunSerializer,
    PresignSerializer,
    RegisterSerializer,
    UploadBatchListSerializer,
    UploadBatchSerializer,
)
from .services import storage

PS = UploadedFile.ParseStatus

OPEN_STATUSES = {UploadBatch.Status.UPLOADING, UploadBatch.Status.READY, UploadBatch.Status.FAILED}
CONFIRMABLE_STATUSES = {
    UploadBatch.Status.READY,
    UploadBatch.Status.DONE,
    UploadBatch.Status.FAILED,
}


class UploadBatchViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsStaff]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    queryset = UploadBatch.objects.select_related("uploaded_by").prefetch_related("files")

    def get_serializer_class(self):
        return UploadBatchListSerializer if self.action == "list" else UploadBatchSerializer

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    def _open_batch(self) -> UploadBatch:
        batch = self.get_object()
        if batch.status not in OPEN_STATUSES:
            raise ValidationError(f"Batch is {batch.status}; wait for it to finish.")
        return batch

    def _after_files_added(self, batch: UploadBatch) -> None:
        batch.status = UploadBatch.Status.GROUPING
        batch.save(update_fields=["status", "updated_at"])
        transaction.on_commit(lambda: tasks.group_batch_task.delay(batch.pk))

    @action(detail=True, methods=["post"])
    def files(self, request, pk=None):
        """Direct upload (multipart, field name ``files``). Fine for dev and small files.

        With ``defer=1`` the files are only stored, so several requests can run at once;
        call ``group`` after the last one. Sending the same file twice stores it once; a
        newer copy of a file (a debugger log the game was still writing) replaces the older.
        """
        batch = self._open_batch()
        uploads = request.FILES.getlist("files")
        if not uploads:
            return Response({"files": ["Attach at least one file."]}, status=400)
        too_big = [f.name for f in uploads if f.size > settings.UPLOAD_MAX_FILE_BYTES]
        if too_big:
            return Response({"files": [f"Too large: {', '.join(too_big)}"]}, status=400)
        defer = str(request.data.get("defer", "")).lower() in {"1", "true", "yes"}
        with transaction.atomic():
            for f in uploads:
                key, size, sha = storage.save_upload(batch.pk, f.name, f)
                if batch.files.filter(original_name=f.name, sha256=sha).exists():
                    default_storage.delete(key)  # a retry of a file that already arrived
                    continue
                for older in batch.files.filter(original_name=f.name):
                    shared = UploadedFile.objects.filter(storage_key=older.storage_key).count() > 1
                    older.delete()
                    if not shared:
                        default_storage.delete(older.storage_key)
                UploadedFile.objects.create(
                    batch=batch, original_name=f.name, storage_key=key, size=size, sha256=sha
                )
            if not defer:
                self._after_files_added(batch)
        batch.refresh_from_db()
        return Response(UploadBatchSerializer(batch).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def known(self, request, pk=None):
        """Which of these files (name and size) the server already has.

        Files already in this batch count (an upload that was cut off and resumed), and
        so do files from earlier uploads: those are added to this batch without sending
        them again. Returns ``{"have": [names]}``; the browser sends only the rest.
        """
        batch = self._open_batch()
        serializer = KnownSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        have = []
        with transaction.atomic():
            for spec in serializer.validated_data["files"]:
                name, size = spec["name"], spec["size"]
                if batch.files.filter(original_name=name, size=size).exists():
                    have.append(name)
                    continue
                original = (
                    UploadedFile.objects.filter(original_name=name, size=size)
                    .exclude(sha256="")
                    .exclude(parse_status__in=[PS.PENDING, PS.FAILED, PS.DUPLICATE])
                    .order_by("created_at")
                    .first()
                )
                if original is None:
                    continue
                UploadedFile.objects.create(
                    batch=batch,
                    original_name=name,
                    kind=original.kind,
                    game_match_id=original.game_match_id,
                    file_timestamp=original.file_timestamp,
                    storage_key=original.storage_key,
                    size=original.size,
                    sha256=original.sha256,
                    parse_status=PS.DUPLICATE,
                    parse_report={"duplicate_of": original.pk},
                )
                have.append(name)
        return Response({"have": have})

    @action(detail=True, methods=["post"])
    def group(self, request, pk=None):
        """Read the files sent with ``defer=1`` and build the preview."""
        batch = self._open_batch()
        if not batch.files.exists():
            return Response({"files": ["Attach at least one file."]}, status=400)
        with transaction.atomic():
            self._after_files_added(batch)
        batch.refresh_from_db()
        return Response(UploadBatchSerializer(batch).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def presign(self, request, pk=None):
        """Upload URLs for big files: the browser PUTs each file straight to S3."""
        batch = self._open_batch()
        if not settings.USE_S3:
            return Response(
                {"detail": "S3 is not configured; use the direct upload endpoint."}, status=400
            )
        serializer = PresignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        out = []
        for spec in serializer.validated_data["files"]:
            key = storage.new_key(batch.pk, spec["name"])
            out.append({"name": spec["name"], "key": key, "url": storage.presigned_put_url(key)})
        return Response({"files": out})

    @action(detail=True, methods=["post"])
    def register(self, request, pk=None):
        """Record files already PUT to S3 through presigned URLs."""
        batch = self._open_batch()
        serializer = RegisterSerializer(data=request.data, context={"batch": batch})
        serializer.is_valid(raise_exception=True)
        missing = [
            f["name"]
            for f in serializer.validated_data["files"]
            if not default_storage.exists(f["key"])
        ]
        if missing:
            return Response({"files": [f"Not uploaded yet: {', '.join(missing)}"]}, status=400)
        with transaction.atomic():
            for f in serializer.validated_data["files"]:
                UploadedFile.objects.get_or_create(
                    batch=batch,
                    storage_key=f["key"],
                    defaults={"original_name": f["name"], "size": f["size"]},
                )
            self._after_files_added(batch)
        batch.refresh_from_db()
        return Response(UploadBatchSerializer(batch).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """Assign each match to a match day / number (and teams), then build them."""
        batch = self.get_object()
        if batch.status not in CONFIRMABLE_STATUSES:
            return Response({"detail": f"Batch is {batch.status}, not ready."}, status=400)
        serializer = ConfirmSerializer(data=request.data, context={"batch": batch})
        serializer.is_valid(raise_exception=True)
        item = serializer.fields["matches"].child
        payload = [item.to_task_payload(m) for m in serializer.validated_data["matches"]]
        batch.status = UploadBatch.Status.PROCESSING
        batch.save(update_fields=["status", "updated_at"])
        user_id = request.user.pk
        transaction.on_commit(lambda: tasks.process_batch_task.delay(batch.pk, payload, user_id))
        return Response({"status": batch.status}, status=status.HTTP_202_ACCEPTED)


class MatchReprocessView(APIView):
    permission_classes = [IsStaff]

    def post(self, request, pk: int):
        match = get_object_or_404(Match, pk=pk, game_match_id__isnull=False)
        user_id = request.user.pk
        transaction.on_commit(lambda: tasks.reprocess_match_task.delay(match.pk, user_id))
        return Response({"status": "queued"}, status=status.HTTP_202_ACCEPTED)


class MatchParseRunsView(ListAPIView):
    permission_classes = [IsStaff]
    serializer_class = ParseRunSerializer

    def get_queryset(self):
        return ParseRun.objects.filter(match_id=self.kwargs["pk"]).select_related("triggered_by")
