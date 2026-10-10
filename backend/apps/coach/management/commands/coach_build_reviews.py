from django.core.management.base import BaseCommand

from apps.coach.models import MatchReview
from apps.coach.moments import RULES, save_reviews
from apps.league.models import Match


class Command(BaseCommand):
    help = (
        "Build the after-match reviews and player counts of every published match that has"
        " none yet or was built with older rules (--all: every match). Run after a deploy"
        " that changes the coach's rules."
    )

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Rebuild every match")

    def handle(self, *args, all=False, **options):
        matches = Match.objects.filter(status=Match.Status.PUBLISHED).order_by("pk")
        if not all:
            fresh = MatchReview.objects.filter(rules=RULES).values_list("match_id", flat=True)
            matches = matches.exclude(pk__in=fresh)
        done = 0
        for pk in matches.values_list("pk", flat=True):
            save_reviews(pk)
            done += 1
        self.stdout.write(f"Built reviews for {done} matches.")
