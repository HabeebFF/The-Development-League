"""Celery tasks for the coach."""

from __future__ import annotations

import logging

from celery import shared_task

from .moments import save_reviews

log = logging.getLogger(__name__)


@shared_task
def build_reviews_task(match_id: int) -> int:
    """Every team's after-match review. A failure here never fails the upload."""
    try:
        return save_reviews(match_id)
    except Exception:
        log.exception("Building reviews for match %s failed", match_id)
        return 0
