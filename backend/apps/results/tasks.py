from celery import shared_task

from apps.league.models import Season

from .standings import rebuild_season


@shared_task
def rebuild_standings_task(season_id: int) -> int:
    season = Season.objects.filter(pk=season_id).first()
    if not season:
        return 0
    rows = rebuild_season(season)
    # Protection Points tasks on those days are checked against the new results too.
    from apps.protection.rules import refresh_season

    refresh_season(season)
    # Player ratings for any match that is new or changed.
    refresh_ratings_task.delay(season.pk)
    return rows


@shared_task
def refresh_ratings_task(season_id: int | None = None, force: bool = False) -> int:
    """Rate the season's matches that are new or changed (every match when ``season_id`` is
    None; every one again when ``force``, after staff change the points)."""
    from apps.league.models import Match

    from .ratings import refresh

    matches = None
    if season_id is not None:
        matches = list(Match.objects.filter(match_day__stage__season_id=season_id))
    rated = refresh(matches, force=force)
    # Daily cards show the day's rating, and the matches may be new too.
    refresh_day_cards_task.delay(season_id)
    return rated


@shared_task
def refresh_day_cards_task(season_id: int | None = None, force: bool = False) -> int:
    """Daily player cards for the days of the season's new or changed matches."""
    from apps.league.models import Match

    from .day_cards import refresh

    matches = None
    if season_id is not None:
        matches = list(
            Match.objects.filter(match_day__stage__season_id=season_id).select_related("match_day")
        )
        matches = [m for m in matches if m.status == Match.Status.PUBLISHED]
    return refresh(matches, force=force)


@shared_task
def weekly_cards_task() -> int:
    """Midnight Lagos (Friday 23:00 UTC): player cards for the week that just ended."""
    from django.utils import timezone

    from .cards import build_week

    return build_week(timezone.now().date())  # still the week's Friday in UTC


@shared_task
def rebuild_cards_task(week: str) -> int:
    """Staff asked for a week's cards again (matches uploaded late, a role changed)."""
    from datetime import date

    from .cards import build_week, card_week, weeks_with_matches

    start = card_week(date.fromisoformat(week))
    # Later weeks compare with this one, so they are rebuilt too.
    return sum(build_week(w) for w in [start, *[w for w in weeks_with_matches() if w > start]])
