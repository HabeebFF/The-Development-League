from celery import shared_task


@shared_task
def open_registrations_task() -> int:
    """Every 5 minutes: a tournament whose registration just opened invites (and freezes) the
    top teams of the standings into its final."""
    from . import entries

    return entries.open_due()
