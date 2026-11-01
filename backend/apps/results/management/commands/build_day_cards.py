from datetime import date

from django.core.management.base import BaseCommand

from apps.results.day_cards import build_day, refresh


class Command(BaseCommand):
    help = "Build daily player cards for match days that are new or changed."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Build every day again")
        parser.add_argument("--date", help="Build just this day (YYYY-MM-DD)")

    def handle(self, *args, **opts):
        if opts["date"]:
            n = build_day(date.fromisoformat(opts["date"]))
            self.stdout.write(f"Built {n} day cards for {opts['date']}.")
            return
        n = refresh(force=opts["all"])
        self.stdout.write(f"Built day cards for {n} days.")
