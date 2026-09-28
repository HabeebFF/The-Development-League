from django.contrib import admin

from .models import DebuggerBlock, ParseRun, UploadBatch, UploadedFile


class UploadedFileInline(admin.TabularInline):
    model = UploadedFile
    extra = 0
    fields = ["original_name", "kind", "game_match_id", "size", "parse_status"]
    readonly_fields = fields


@admin.register(UploadBatch)
class UploadBatchAdmin(admin.ModelAdmin):
    list_display = ["id", "status", "uploaded_by", "note", "created_at"]
    list_filter = ["status"]
    inlines = [UploadedFileInline]
    readonly_fields = ["preview", "error"]


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ["original_name", "kind", "game_match_id", "parse_status", "batch"]
    list_filter = ["kind", "parse_status"]
    search_fields = ["original_name", "game_match_id"]
    readonly_fields = ["parse_report", "sha256", "storage_key"]


@admin.register(DebuggerBlock)
class DebuggerBlockAdmin(admin.ModelAdmin):
    list_display = ["file", "game_match_id", "game_map_id", "start_line", "end_line", "started_at"]


@admin.register(ParseRun)
class ParseRunAdmin(admin.ModelAdmin):
    list_display = ["id", "match", "status", "triggered_by", "created_at"]
    list_filter = ["status"]
    readonly_fields = ["sources", "counts", "warnings", "error"]
