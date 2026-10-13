from django.core.management.base import BaseCommand

from apps.results.ratings import refresh


class Command(BaseCommand):
    help = "Work out player ratings (out of 10) for published matches that are new or changed."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Rate every match again")

    def handle(self, *args, **opts):
        n = refresh(force=opts["all"])
        self.stdout.write(f"Rated {n} matches.")
