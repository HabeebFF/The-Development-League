from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.coach.reports import week_of, write_reports


class Command(BaseCommand):
    help = (
        "Write (or refresh) every league team's coach report for a week (default: this week)."
        " With the AI writer on, calls are paced to its per-minute limit."
    )

    def add_arguments(self, parser):
        parser.add_argument("--week", help="Any day in the week, YYYY-MM-DD")

    def handle(self, *args, week=None, **options):
        day = date.fromisoformat(week) if week else timezone.localdate()
        start = week_of(day)
        count = write_reports(start, wait=True)
        self.stdout.write(f"Wrote {count} reports for the week of {start}.")
