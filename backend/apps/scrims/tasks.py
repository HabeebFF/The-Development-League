from celery import shared_task

from . import services


@shared_task
def wrap_scrims_task() -> int:
    """Every 5 minutes: sessions whose sign-up has closed drop invites nobody confirmed, move
    waitlisted teams into free places and refund the teams still waiting."""
    return services.wrap_due()
