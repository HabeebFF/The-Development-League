from celery import shared_task

from . import services


@shared_task
def wrap_scrims_task() -> int:
    """Every 5 minutes: sessions whose sign-up has closed drop invites nobody confirmed, move
    waitlisted teams into free places and refund the teams still waiting."""
    return services.wrap_due()


@shared_task
def draw_maps_task() -> int:
    """Every 5 minutes: draw the maps of sessions whose sign-up has just opened."""
    from . import maps

    return maps.draw_due()
