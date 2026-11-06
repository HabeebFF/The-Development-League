"""List account names with 18+ or offensive words; ``--fix`` renames them.

    python manage.py check_names          # just list them
    python manage.py check_names --fix    # rename each to "Player <id>"

The owner sees "Pick another name" next time they change it. In-game player names come
from match logs, so those are only listed (they can't be renamed here).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.league.models import Player
from common.names import blocked_word


class Command(BaseCommand):
    help = "Find (and with --fix rename) account names with 18+ or offensive words."

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true", help='Rename them to "Player <id>"')

    def handle(self, *args, **opts):
        users = [
            (u, w)
            for u in User.objects.exclude(display_name="").only("pk", "display_name")
            if (w := blocked_word(u.display_name))
        ]
        for user, word in users:
            self.stdout.write(f"account {user.pk}: {user.display_name!r} (matched {word!r})")
        if opts["fix"]:
            with transaction.atomic():
                for user, _ in users:
                    User.objects.filter(pk=user.pk).update(display_name=f"Player {user.pk}")
            self.stdout.write(f"Renamed {len(users)} account(s).")
        players = [
            (p, w)
            for p in Player.objects.only("pk", "display_name")
            if (w := blocked_word(p.display_name))
        ]
        for player, word in players:
            self.stdout.write(
                f"in-game player {player.pk}: {player.display_name!r} (matched {word!r})"
            )
        self.stdout.write(f"{len(users)} account name(s), {len(players)} in-game name(s) flagged.")
