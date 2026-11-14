from datetime import date

from django.core.management.base import BaseCommand

from apps.results.cards import mark_award_winners
from apps.results.models import PlayerCard


class Command(BaseCommand):
    help = (
        "Work out every card week's award winners again and write them onto the cards (the"
        " award badges), without rebuilding the cards themselves (--week YYYY-MM-DD: just that"
        " week). Run after a deploy that changes the award rules."
    )

    def add_arguments(self, parser):
        parser.add_argument("--week", help="Any day of the one week to refresh")

    def handle(self, *args, week=None, **options):
        if week:
            weeks = [date.fromisoformat(week)]
        else:
            weeks = sorted(set(PlayerCard.objects.values_list("week", flat=True)))
        total = 0
        for w in weeks:
            n = mark_award_winners(w)
            total += n
            self.stdout.write(f"Week of {w}: {n} cards changed.")
        self.stdout.write(f"Done: {total} cards changed.")
