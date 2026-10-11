from datetime import date

from django.core.management.base import BaseCommand

from apps.results.cards import build_week, weeks_with_matches


class Command(BaseCommand):
    help = (
        "Build the player cards of every week with published matches, oldest first, so each"
        " week's ups and downs compare with the week before (--week YYYY-MM-DD: just that"
        " week). Run once after the deploy that adds cards, and after late uploads."
    )

    def add_arguments(self, parser):
        parser.add_argument("--week", help="Any day of the one week to build")

    def handle(self, *args, week=None, **options):
        weeks = [date.fromisoformat(week)] if week else weeks_with_matches()
        for w in weeks:
            n = build_week(w)
            self.stdout.write(f"Week of {w}: {n} cards.")
