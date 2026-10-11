from datetime import date

from django.core.management.base import BaseCommand

from apps.results.cards import build_week, weeks_with_matches
from apps.results.models import PlayerCard


class Command(BaseCommand):
    help = (
        "Build the player cards of every card week (Saturday to Friday) that is already out,"
        " oldest first, so each week's ups and downs compare with the week before (--week"
        " YYYY-MM-DD: just that week). Cards left from the old Monday weeks are removed."
        " Run after a deploy that changes cards, and after late uploads."
    )

    def add_arguments(self, parser):
        parser.add_argument("--week", help="Any day of the one week to build")

    def handle(self, *args, week=None, **options):
        stale = PlayerCard.objects.exclude(week__week_day=7).delete()[0]  # 7 = Saturday
        if stale:
            self.stdout.write(f"Removed {stale} cards from the old Monday weeks.")
        weeks = [date.fromisoformat(week)] if week else weeks_with_matches()
        for w in weeks:
            n = build_week(w)
            self.stdout.write(f"Week of {w}: {n} cards.")
