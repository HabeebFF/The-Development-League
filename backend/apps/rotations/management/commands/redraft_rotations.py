"""Rebuild every match's auto-drafted rotations (staff-edited ones are kept).

Run after a deploy that changes how rotations are drafted, e.g. to move auto points onto
the replay paths: ``python manage.py redraft_rotations``.
"""

from django.core.management.base import BaseCommand

from apps.league.models import Match
from apps.rotations.auto import draft_rotations


class Command(BaseCommand):
    help = "Rebuild AUTO rotations of every match (or --match <id>), keeping staff edits."

    def add_arguments(self, parser):
        parser.add_argument("--match", type=int, action="append", help="Only this match id.")

    def handle(self, *args, **options):
        matches = Match.objects.filter(team_results__isnull=False).distinct().order_by("pk")
        if options["match"]:
            matches = matches.filter(pk__in=options["match"])
        total = 0
        for match in matches:
            total += draft_rotations(match)
        self.stdout.write(f"Redrafted {total} team rotations in {matches.count()} matches.")
