from django.core.management.base import BaseCommand

from apps.ingest.services import storage
from apps.ingest.services.assemble import latest_sources
from apps.league.models import Match

from ...damage import build_damage


class Command(BaseCommand):
    help = (
        "Work out damage dealt and taken for matches uploaded before damage was read, from "
        "each match's stored replay .bin. Matches without one are left as they are."
    )

    def handle(self, *args, **opts):
        done = skipped = 0
        for match in Match.objects.filter(game_match_id__isnull=False).order_by("pk"):
            source = latest_sources(match.game_match_id).replay_bin
            if source is None:
                skipped += 1
                continue
            problem = build_damage(match, storage.read_bytes(source.storage_key))
            if problem:
                self.stdout.write(f"{match}: {problem}")
            done += 1
        self.stdout.write(f"Damage read for {done} matches; {skipped} have no replay .bin.")
