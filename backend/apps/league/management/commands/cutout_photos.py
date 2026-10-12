from django.core.management.base import BaseCommand

from apps.league.models import Player
from apps.league.photos import make_cutout


class Command(BaseCommand):
    help = (
        "Cut the background out of player photos and frame them for the cards (--all: redo the"
        " ones already done too). The first run downloads the 170 MB person model."
    )

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Redo every photo")

    def handle(self, *args, all=False, **options):
        players = Player.objects.exclude(photo="")
        if not all:
            players = players.filter(photo_cutout="")
        for p in players:
            ok = make_cutout(p)
            self.stdout.write(f"{p.display_name}: {'done' if ok else 'failed, photo kept as is'}")
