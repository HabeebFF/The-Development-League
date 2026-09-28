"""Read every new file in a batch, then build the per-match preview staff confirm.

Small files are parsed here so the preview can show teams, map and room name. A
debugger log is scanned once and split into ``DebuggerBlock`` rows (one per match);
the blocks are re-read by byte range when a match is assembled.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.league.models import Match, TeamAlias
from apps.maps.models import Map

from ..models import DebuggerBlock, UploadBatch, UploadedFile
from ..parsers import debugger, match_id, match_result, replay_info, safe_zone
from ..parsers.base import ParseResult
from ..parsers.filenames import FileKind, classify
from . import storage

PS = UploadedFile.ParseStatus
# How long after a debugger block starts its MatchResult may be written.
TIME_LINK_WINDOW = timedelta(minutes=40)
_DAY_IN_ROOM = re.compile(r"\bDAY\s*(\d+)\b", re.IGNORECASE)


def log_time(value: datetime | None) -> datetime | None:
    """Observer times are local and zone-less; read them in LOG_TIME_ZONE."""
    if value is None or timezone.is_aware(value):
        return value
    return value.replace(tzinfo=ZoneInfo(settings.LOG_TIME_ZONE))


def report(result: ParseResult, **extra: Any) -> dict[str, Any]:
    return {
        "warnings": [
            {"code": w.code, "message": w.message, "line_no": w.line_no, "line": w.line}
            for w in result.warnings
        ],
        "warning_count": result.warning_count,
        "stats": {
            "lines": result.stats.lines,
            "parsed": result.stats.parsed,
            "skipped": result.stats.skipped,
        },
        **extra,
    }


def status_for(result: ParseResult) -> str:
    if result.data is None:
        return PS.FAILED
    return PS.WARNINGS if result.warning_count else PS.OK


# -- Reading single files ----------------------------------------------------------------


def read_file(upload: UploadedFile) -> None:
    """Classify, de-duplicate and parse one file; saves the result on the row."""
    info = classify(upload.original_name)
    upload.kind = info.kind
    upload.game_match_id = info.match_id
    upload.file_timestamp = log_time(info.timestamp)

    if not upload.sha256:
        upload.sha256, upload.size = storage.sha256_of(upload.storage_key)
    original = (
        UploadedFile.objects.filter(sha256=upload.sha256)
        .exclude(pk=upload.pk)
        .exclude(parse_status__in=[PS.DUPLICATE, PS.FAILED, PS.PENDING])
        .order_by("created_at")
        .first()
    )
    if original is not None:
        upload.parse_status = PS.DUPLICATE
        upload.parse_report = {"duplicate_of": original.pk}
        upload.save()
        return

    try:
        _parse(upload, info.kind)
    except Exception as exc:  # a broken file must never break the batch
        upload.parse_status = PS.FAILED
        upload.parse_report = {"error": f"{type(exc).__name__}: {exc}"}
    upload.save()


def _parse(upload: UploadedFile, kind: FileKind) -> None:
    name, key = upload.original_name, upload.storage_key

    if kind is FileKind.MATCH_RESULT:
        result = match_result.parse(name, storage.read_bytes(key))
        teams = [
            {
                "in_game_name": t.name_raw,
                "display_name": t.name,
                "rank": t.rank,
                "kills": t.kill_score,
                "total": t.total_score,
                "players": len(t.players),
            }
            for t in (result.data.teams if result.data else [])
        ]
        upload.parse_status = PS.FAILED if not teams else status_for(result)
        upload.parse_report = report(result, teams=teams)

    elif kind is FileKind.REPLAY_JSON:
        result = replay_info.parse(name, storage.read_bytes(key))
        data = result.data
        meta = {}
        if data is not None:
            if upload.game_match_id is None:
                upload.game_match_id = data.match_id
            meta = {
                "map_id": data.map_id,
                "room_name": data.room_name,
                "started_at": log_time(data.started_at).isoformat() if data.started_at else None,
                "duration_s": data.duration_s,
                "kills": len(data.kills),
            }
        upload.parse_status = status_for(result)
        upload.parse_report = report(result, meta=meta)

    elif kind is FileKind.SAFE_ZONE:
        result = safe_zone.parse(name, storage.read_bytes(key))
        point = {"x": result.data.x, "z": result.data.z} if result.data else None
        upload.parse_status = status_for(result)
        upload.parse_report = report(result, point=point)

    elif kind is FileKind.MATCH_ID:
        result = match_id.parse(name, storage.read_bytes(key))
        upload.parse_status = status_for(result)
        upload.parse_report = report(result)

    elif kind is FileKind.DEBUGGER:
        _scan_debugger(upload)

    elif kind is FileKind.REPLAY_BIN:
        upload.parse_status = PS.SKIPPED
        upload.parse_report = {"note": "Binary replay stored, not parsed"}

    else:
        upload.parse_status = PS.SKIPPED
        upload.parse_report = {"note": "Not a recognised log file name; stored only"}


def _scan_debugger(upload: UploadedFile) -> None:
    result: ParseResult[debugger.DebuggerSession] = ParseResult(debugger.DebuggerSession())
    blocks = list(debugger.iter_blocks(storage.iter_lines(upload.storage_key), result))
    upload.blocks.all().delete()
    rows = []
    for i, block in enumerate(blocks):
        start = block.start_offset or 0
        end = blocks[i + 1].start_offset if i + 1 < len(blocks) else upload.size
        rows.append(
            DebuggerBlock(
                file=upload,
                game_match_id=block.match_id,
                game_map_id=block.map_id,
                start_line=block.start_line,
                end_line=block.end_line,
                byte_start=start,
                byte_end=end if end is not None else upload.size,
                started_at=log_time(block.started_at),
                ended_at=log_time(block.ended_at),
                summary=block.summary(),
            )
        )
    DebuggerBlock.objects.bulk_create(rows)
    session = result.data
    upload.parse_status = PS.FAILED if not blocks else status_for(result)
    upload.parse_report = report(
        result,
        matches=len(blocks),
        lines_without_header=session.lines_without_header if session else 0,
    )


# -- Linking and preview -------------------------------------------------------------------


def link_blocks_by_time(batch: UploadBatch) -> None:
    """Give match ids to debugger blocks that had no end line, using MatchResult times."""
    results = [
        f
        for f in batch.files.filter(kind=FileKind.MATCH_RESULT, file_timestamp__isnull=False)
        .exclude(parse_status__in=[PS.FAILED, PS.DUPLICATE])
        .order_by("file_timestamp")
    ]
    taken = set(
        DebuggerBlock.objects.filter(file__batch=batch, game_match_id__isnull=False).values_list(
            "game_match_id", flat=True
        )
    )
    for block in DebuggerBlock.objects.filter(file__batch=batch, game_match_id__isnull=True):
        for f in results:
            if f.game_match_id in taken:
                continue
            if block.started_at <= f.file_timestamp <= block.started_at + TIME_LINK_WINDOW:
                block.game_match_id = f.game_match_id
                block.summary = {**block.summary, "match_id": f.game_match_id, "linked_by": "time"}
                block.save(update_fields=["game_match_id", "summary", "updated_at"])
                taken.add(f.game_match_id)
                break


def build_preview(batch: UploadBatch) -> dict[str, Any]:
    by_match: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"files": [], "blocks": [], "warnings": []}
    )
    unassigned = []
    for f in batch.files.order_by("original_name"):
        entry = {"id": f.pk, "name": f.original_name, "kind": f.kind, "status": f.parse_status}
        if f.game_match_id is not None and f.kind != FileKind.DEBUGGER:
            by_match[f.game_match_id]["files"].append(entry)
        elif f.kind != FileKind.DEBUGGER:
            unassigned.append(entry)
    unlinked_blocks = 0
    for block in DebuggerBlock.objects.filter(file__batch=batch).select_related("file"):
        if block.game_match_id is None:
            unlinked_blocks += 1
            continue
        by_match[block.game_match_id]["blocks"].append(
            {"id": block.pk, "file": block.file.original_name, "summary": block.summary}
        )

    matches = [_preview_match(gid, data) for gid, data in sorted(by_match.items())]
    return {
        "matches": matches,
        "unassigned_files": unassigned,
        "unlinked_debugger_blocks": unlinked_blocks,
    }


def _preview_match(game_match_id: int, data: dict[str, Any]) -> dict[str, Any]:
    from .assemble import latest_sources  # avoid an import cycle

    sources = latest_sources(game_match_id)
    existing = (
        Match.objects.select_related("match_day__stage__season")
        .filter(game_match_id=game_match_id)
        .first()
    )
    season = existing.season if existing else None

    teams = []
    if sources.match_result is not None:
        for t in sources.match_result.parse_report.get("teams", []):
            team = TeamAlias.resolve(t["in_game_name"], season)
            teams.append({**t, "team": {"id": team.pk, "name": team.name} if team else None})

    meta = sources.replay.parse_report.get("meta", {}) if sources.replay else {}
    game_map_id = meta.get("map_id")
    if game_map_id is None and sources.block is not None:
        game_map_id = sources.block.game_map_id
    game_map = Map.objects.filter(game_map_id=game_map_id).first() if game_map_id else None
    room_name = meta.get("room_name") or ""
    day = _DAY_IN_ROOM.search(room_name)

    warnings = list(data["warnings"])
    if sources.match_result is None:
        warnings.append("No MatchResult file yet: the match cannot be scored.")
    if teams and any(t["team"] is None for t in teams):
        warnings.append("Some in-game team names are not linked to a league team yet.")

    return {
        "game_match_id": str(game_match_id),  # 19 digits: too big for JavaScript numbers
        "files": data["files"],
        "debugger_blocks": data["blocks"],
        "has_match_result": sources.match_result is not None,
        "has_replay_info": sources.replay is not None,
        "has_debugger": sources.block is not None,
        "room_name": room_name,
        "started_at": meta.get("started_at")
        or (sources.block.started_at.isoformat() if sources.block else None),
        "game_map_id": game_map_id,
        "map": {"id": game_map.pk, "name": game_map.name} if game_map else None,
        "match_day_hint": int(day[1]) if day else None,
        "teams": teams,
        "existing_match": (
            {
                "id": existing.pk,
                "match_day": existing.match_day_id,
                "number": existing.number,
                "status": existing.status,
            }
            if existing
            else None
        ),
        "ready": sources.match_result is not None or existing is not None,
        "warnings": warnings,
    }


def group_batch(batch_id: int) -> UploadBatch:
    """Read new files and rebuild the preview. Safe to run again at any time."""
    with transaction.atomic():
        batch = UploadBatch.objects.select_for_update().get(pk=batch_id)
        batch.status = UploadBatch.Status.GROUPING
        batch.save(update_fields=["status", "updated_at"])
        for upload in batch.files.filter(parse_status=PS.PENDING):
            read_file(upload)
        link_blocks_by_time(batch)
        batch.preview = build_preview(batch)
        batch.status = UploadBatch.Status.READY
        batch.error = ""
        batch.save(update_fields=["preview", "status", "error", "updated_at"])
    return batch
