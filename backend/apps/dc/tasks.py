import logging

from celery import shared_task

log = logging.getLogger(__name__)


@shared_task
def sync_match_task(match_id: int) -> dict:
    """After an upload: pay the match's DC (kills, Booyah, MVP, played)."""
    from .rewards import sync_match

    return sync_match(match_id)


@shared_task
def sync_season_task(season_id: int) -> int:
    """After ratings change (the MVP may move): bring the season's matches up to date."""
    from apps.league.models import Match

    from .models import DcSettings
    from .rewards import enabled, sync_match

    if not enabled():
        return 0
    conf = DcSettings.get()
    matches = Match.objects.filter(
        match_day__stage__season_id=season_id, match_day__date__gte=conf.start_date
    ).select_related("match_day")
    return sum(1 for m in matches if sync_match(m, conf=conf).get("players"))


@shared_task
def sweep_task() -> dict:
    """Every 5 minutes: recent matches, and DC waiting for players who just linked."""
    from .rewards import sweep

    report = sweep()
    if report.get("paid_waiting"):
        log.info("DC rewards: %s", report)
    return report


@shared_task
def pay_waiting_task(player_id: int) -> int:
    from .rewards import pay_waiting

    return pay_waiting(player_id)


@shared_task
def crown_task() -> int | None:
    """Daily, early morning: make last month's DC King if it isn't made yet."""
    from django.core.cache import cache

    from .ranks import crown_last_month

    s = crown_last_month()
    cache.delete("dc:board")
    return s.pk if s else None
