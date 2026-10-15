from django.core.management.base import BaseCommand, CommandError

from apps.predictions.services import check_wallets


class Command(BaseCommand):
    help = "Check that every wallet's balance matches its ledger."

    def handle(self, *args, **options):
        problems = check_wallets()
        for p in problems:
            self.stdout.write(f"Wallet {p.wallet_id}: {p.problem}")
        if problems:
            raise CommandError(f"{len(problems)} problem(s) found.")
        self.stdout.write(self.style.SUCCESS("Every wallet adds up."))
