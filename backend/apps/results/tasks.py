from celery import shared_task

from apps.league.models import Season

from .standings import rebuild_season


@shared_task
def rebuild_standings_task(season_id: int) -> int:
    season = Season.objects.filter(pk=season_id).first()
    return rebuild_season(season) if season else 0
