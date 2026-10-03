from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.coach import research
from apps.coach.models import KnowledgeEntry
from apps.maps.models import Map, MapArea


class Command(BaseCommand):
    help = "Load researched knowledge as drafts (staff-written entries are never overwritten)."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(research.LATEST))

    def handle(self, *args, **opts):
        with transaction.atomic():
            counts = research.load(research.read(Path(opts["file"])), KnowledgeEntry, Map, MapArea)
        self.stdout.write(", ".join(f"{k}: {v}" for k, v in counts.items()))
