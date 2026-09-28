"""Staff upload API.

Flow: create a batch -> add files (direct upload, or presign + PUT to S3 + register)
-> files are read in the background and a per-match preview appears on the batch
-> confirm with a match day / number per match -> matches are built in the background.
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
    ParseRunSerializer,
    PresignSerializer,
    RegisterSerializer,
    UploadBatchListSerializer,
    UploadBatchSerializer,
)
from .services import storage

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
        """Direct upload (multipart, field name ``files``). Fine for dev and small files."""
        batch = self._open_batch()
        uploads = request.FILES.getlist("files")
        if not uploads:
            return Response({"files": ["Attach at least one file."]}, status=400)
        too_big = [f.name for f in uploads if f.size > settings.UPLOAD_MAX_FILE_BYTES]
        if too_big:
            return Response({"files": [f"Too large: {', '.join(too_big)}"]}, status=400)
        with transaction.atomic():
            for f in uploads:
                key, size, sha = storage.save_upload(batch.pk, f.name, f)
                UploadedFile.objects.create(
                    batch=batch, original_name=f.name, storage_key=key, size=size, sha256=sha
                )
            self._after_files_added(batch)
        batch.refresh_from_db()
        return Response(UploadBatchSerializer(batch).data, status=status.HTTP_201_CREATED)

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
