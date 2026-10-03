"""Rebuild every match's team routes (and AUTO rotation points) from the stored tracks."""

from django.core.management.base import BaseCommand

from apps.league.models import Match
from apps.rotations.auto import draft_rotations


class Command(BaseCommand):
    help = "Rebuild team routes from the replay tracks; staff-edited points are kept."

    def add_arguments(self, parser):
        parser.add_argument("match_ids", nargs="*", type=int, help="Only these matches")

    def handle(self, *args, match_ids, **options):
        matches = Match.objects.order_by("pk")
        if match_ids:
            matches = matches.filter(pk__in=match_ids)
        for match in matches:
            drafted = draft_rotations(match)
            self.stdout.write(f"match {match.pk}: {drafted} auto rotation(s) redrafted")
