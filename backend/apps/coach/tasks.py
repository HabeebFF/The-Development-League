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


@shared_task
def weekly_reports_task() -> int:
    """Monday morning: every league team's report for the new week."""
    from django.utils import timezone

    from .reports import week_of, write_reports

    return write_reports(week_of(timezone.localdate()), wait=True)


@shared_task
def catch_up_reviews_task() -> int:
    """Nightly safety net: reviews for any published match that has none (or old ones)."""
    from apps.league.models import Match

    from .models import MatchReview
    from .moments import RULES

    fresh = MatchReview.objects.filter(rules=RULES).values_list("match_id", flat=True)
    done = 0
    for pk in (
        Match.objects.filter(status=Match.Status.PUBLISHED)
        .exclude(pk__in=fresh)
        .values_list("pk", flat=True)
    ):
        done += build_reviews_task(pk)
    return done
