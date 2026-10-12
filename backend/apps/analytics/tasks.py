"""Celery tasks for visitor analytics."""

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import PageView

KEEP_DAYS = 400  # about 13 months


@shared_task
def purge_old_views_task() -> int:
    """Nightly: drop page views older than about 13 months to keep the database small."""
    cutoff = timezone.now() - timedelta(days=KEEP_DAYS)
    deleted, _ = PageView.objects.filter(created_at__lt=cutoff).delete()
    return deleted
