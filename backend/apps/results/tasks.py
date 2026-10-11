from celery import shared_task

from apps.league.models import Season

from .standings import rebuild_season


@shared_task
def rebuild_standings_task(season_id: int) -> int:
    season = Season.objects.filter(pk=season_id).first()
    return rebuild_season(season) if season else 0


@shared_task
def weekly_cards_task() -> int:
    """Monday morning: player cards for the week that just ended (Monday to Sunday)."""
    from datetime import timedelta

    from django.utils import timezone

    from .cards import build_week

    return build_week(timezone.localdate() - timedelta(days=1))


@shared_task
def rebuild_cards_task(week: str) -> int:
    """Staff asked for a week's cards again (matches uploaded late, a role changed)."""
    from datetime import date

    from .awards import period_of
    from .cards import build_week, weeks_with_matches

    start = period_of("week", date.fromisoformat(week))[0]
    # Later weeks compare with this one, so they are rebuilt too.
    return sum(build_week(w) for w in [start, *[w for w in weeks_with_matches() if w > start]])
