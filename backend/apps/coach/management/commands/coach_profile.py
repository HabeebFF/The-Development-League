from django.core.management.base import BaseCommand, CommandError

from apps.coach.engine import team_profile
from apps.league.models import Team


class Command(BaseCommand):
    help = "Print what the coach's analysis engine found about a team (its facts)."

    def add_arguments(self, parser):
        parser.add_argument("team", help="Team slug")

    def handle(self, *args, team, **options):
        try:
            t = Team.objects.get(slug=team)
        except Team.DoesNotExist as e:
            raise CommandError(f"No team {team!r}") from e
        result = team_profile(t.pk)
        self.stdout.write(f"{t.name}: {result['matches']} matches {result['maps']}")
        for f in result["facts"]:
            self.stdout.write(f"  [{f['id']}] {f['text']}  ({f['n']}/{f['of']} matches)")
