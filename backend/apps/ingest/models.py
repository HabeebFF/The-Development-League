"""Uploads: batches of files, what they contain, and each processing run."""

from django.conf import settings
from django.db import models

from common.models import TimeStampedModel

from .parsers.filenames import FileKind


class UploadBatch(TimeStampedModel):
    class Status(models.TextChoices):
        UPLOADING = "UPLOADING", "Uploading"
        GROUPING = "GROUPING", "Reading files"
        READY = "READY", "Ready to confirm"
        PROCESSING = "PROCESSING", "Processing"
        DONE = "DONE", "Done"
        FAILED = "FAILED", "Failed"

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="upload_batches"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.UPLOADING)
    note = models.CharField(max_length=200, blank=True)
    preview = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "upload batches"

    def __str__(self) -> str:
        return f"Batch {self.pk} ({self.status})"


class UploadedFile(TimeStampedModel):
    class ParseStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        OK = "OK", "Read"
        WARNINGS = "WARNINGS", "Read with warnings"
        FAILED = "FAILED", "Could not read"
        SKIPPED = "SKIPPED", "Stored only"
        DUPLICATE = "DUPLICATE", "Same file already uploaded"

    batch = models.ForeignKey(UploadBatch, on_delete=models.CASCADE, related_name="files")
    original_name = models.CharField(max_length=255)
    kind = models.CharField(
        max_length=16, choices=[(k.value, k.value) for k in FileKind], default=FileKind.UNKNOWN
    )
    game_match_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    file_timestamp = models.DateTimeField(null=True, blank=True)
    storage_key = models.CharField(max_length=500)
    size = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    parse_status = models.CharField(
        max_length=10, choices=ParseStatus.choices, default=ParseStatus.PENDING
    )
    parse_report = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["batch", "original_name"]

    def __str__(self) -> str:
        return self.original_name


class DebuggerBlock(TimeStampedModel):
    """Where one match sits inside a session debugger log."""

    file = models.ForeignKey(UploadedFile, on_delete=models.CASCADE, related_name="blocks")
    game_match_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    game_map_id = models.IntegerField(null=True, blank=True)
    start_line = models.PositiveIntegerField()
    end_line = models.PositiveIntegerField(null=True, blank=True)
    byte_start = models.BigIntegerField()
    byte_end = models.BigIntegerField(help_text="Exclusive; start of the next block or EOF")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    summary = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["file", "start_line"]

    def __str__(self) -> str:
        return f"{self.file} lines {self.start_line}-{self.end_line}"


class ParseRun(TimeStampedModel):
    class Status(models.TextChoices):
        RUNNING = "RUNNING", "Running"
        OK = "OK", "OK"
        WARNINGS = "WARNINGS", "OK with warnings"
        FAILED = "FAILED", "Failed"

    match = models.ForeignKey("league.Match", on_delete=models.CASCADE, related_name="parse_runs")
    batch = models.ForeignKey(
        UploadBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name="parse_runs"
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    finished_at = models.DateTimeField(null=True, blank=True)
    sources = models.JSONField(default=dict, blank=True)
    counts = models.JSONField(default=dict, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Run {self.pk} for {self.match} ({self.status})"
