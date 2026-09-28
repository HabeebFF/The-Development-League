"""Celery tasks for uploads. Each task is safe to run again."""

from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from apps.league.models import Match, MatchDay
from apps.maps.models import Map

from .models import ParseRun, UploadBatch
from .services.assemble import AssembleError, Assignment, assemble
from .services.grouping import build_preview, group_batch

log = logging.getLogger(__name__)


@shared_task
def group_batch_task(batch_id: int) -> None:
    try:
        group_batch(batch_id)
    except Exception as exc:
        log.exception("Grouping batch %s failed", batch_id)
        UploadBatch.objects.filter(pk=batch_id).update(
            status=UploadBatch.Status.FAILED, error=f"{type(exc).__name__}: {exc}"
        )
        raise


@shared_task
def process_batch_task(batch_id: int, assignments: list[dict], user_id: int | None) -> None:
    """Assemble every confirmed match of a batch, one after another."""
    batch = UploadBatch.objects.get(pk=batch_id)
    user = get_user_model().objects.filter(pk=user_id).first()
    results = []
    for item in assignments:
        game_match_id = int(item["game_match_id"])
        try:
            run = assemble(_assignment(item), batch=batch, user=user)
            results.append(
                {
                    "game_match_id": str(game_match_id),
                    "match_id": run.match_id,
                    "status": run.status,
                    "error": run.error,
                }
            )
        except AssembleError as exc:
            results.append(
                {"game_match_id": str(game_match_id), "status": "FAILED", "error": str(exc)}
            )
    ok = any(r["status"] != ParseRun.Status.FAILED for r in results)
    batch.preview = {**build_preview(batch), "results": results}
    batch.status = UploadBatch.Status.DONE if ok else UploadBatch.Status.FAILED
    batch.save(update_fields=["preview", "status", "updated_at"])


@shared_task
def reprocess_match_task(match_id: int, user_id: int | None) -> None:
    match = Match.objects.get(pk=match_id)
    user = get_user_model().objects.filter(pk=user_id).first()
    assemble(Assignment(game_match_id=match.game_match_id), user=user)


def _assignment(item: dict) -> Assignment:
    return Assignment(
        game_match_id=int(item["game_match_id"]),
        match_day=MatchDay.objects.filter(pk=item.get("match_day")).first()
        if item.get("match_day")
        else None,
        number=item.get("number"),
        map=Map.objects.filter(pk=item.get("map")).first() if item.get("map") else None,
        team_ids={name: int(tid) for name, tid in (item.get("teams") or {}).items()},
        create_missing_teams=item.get("create_missing_teams", True),
    )
