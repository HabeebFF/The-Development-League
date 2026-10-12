"""Starting PP for a period from a pasted table file ("1. BERSERK GEN — +4 PP" per line)."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.protection.models import Period
from apps.protection.rules import parse_table, set_starting


class Command(BaseCommand):
    help = "Set a PP period's starting PP from a text file of the old table."

    def add_arguments(self, parser):
        parser.add_argument("period", type=int, help="Period id")
        parser.add_argument("file", type=Path)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, period, file, dry_run, **options):
        p = Period.objects.filter(pk=period).first()
        if not p:
            raise CommandError(f"No period {period}")
        found, missing = parse_table(file.read_text(encoding="utf-8"))
        for team, pp, name in found:
            self.stdout.write(f"{name} -> {team.name}: {pp:+d}")
        for name in missing:
            self.stdout.write(self.style.WARNING(f"Not found: {name}"))
        if missing:
            raise CommandError("Some teams were not found; add aliases or fix the names first.")
        if not dry_run:
            set_starting(p, found)
            self.stdout.write(self.style.SUCCESS(f"Saved {len(found)} teams."))
