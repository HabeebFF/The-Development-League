from celery import shared_task

from apps.league.models import Season

from .standings import rebuild_season


@shared_task
def rebuild_standings_task(season_id: int) -> int:
    season = Season.objects.filter(pk=season_id).first()
    return rebuild_season(season) if season else 0


@shared_task
def weekly_cards_task() -> int:
    """Saturday 11:00 Lagos: player cards for the week that just ended (Saturday to Friday)."""
    from datetime import timedelta

    from django.utils import timezone

    from .cards import build_week

    return build_week(timezone.now().date() - timedelta(days=1))


@shared_task
def rebuild_cards_task(week: str) -> int:
    """Staff asked for a week's cards again (matches uploaded late, a role changed)."""
    from datetime import date

    from .cards import build_week, card_week, weeks_with_matches

    start = card_week(date.fromisoformat(week))
    # Later weeks compare with this one, so they are rebuilt too.
    return sum(build_week(w) for w in [start, *[w for w in weeks_with_matches() if w > start]])
