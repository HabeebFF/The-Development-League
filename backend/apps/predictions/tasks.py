import logging

from celery import shared_task

from . import auto
from .markets import close_due_markets
from .services import check_wallets

log = logging.getLogger(__name__)


@shared_task
def check_wallets_task() -> int:
    """Nightly: every wallet's balance must match its ledger. Logs any that don't."""
    problems = check_wallets()
    for p in problems:
        log.error("Wallet %s does not add up: %s", p.wallet_id, p.problem)
    return len(problems)


@shared_task
def close_due_markets_task() -> int:
    """Every minute: markets past their closing time show as closed."""
    return close_due_markets()


@shared_task
def auto_markets_task() -> int:
    """Hourly: on a scrim day from 10:00 Lagos time, make tonight's missing markets."""
    report = auto.run()
    for note in report["notes"]:
        log.info("Automatic markets %s: %s", report["date"], note)
    return len(report["made"])
