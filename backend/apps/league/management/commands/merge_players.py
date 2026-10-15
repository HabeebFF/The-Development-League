from django.core.management.base import BaseCommand, CommandError

from apps.league.merge import MergeError, merge_players
from apps.league.models import Player


class Command(BaseCommand):
    help = "Merge one player into another (the same person): merge_players SOURCE_ID INTO_ID"

    def add_arguments(self, parser):
        parser.add_argument("source", type=int)
        parser.add_argument("into", type=int)

    def handle(self, *args, **opts):
        try:
            source = Player.objects.get(pk=opts["source"])
            target = Player.objects.get(pk=opts["into"])
            result = merge_players(source, target)
        except (Player.DoesNotExist, MergeError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(str(result))
