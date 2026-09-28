from django.core.management.base import BaseCommand

from apps.maps.bundled import install_all


class Command(BaseCommand):
    help = "Give maps the images (and calibration) bundled in apps/maps/default_images."

    def add_arguments(self, parser):
        parser.add_argument("slugs", nargs="*", help="Only these maps (default: all)")
        parser.add_argument(
            "--force", action="store_true", help="Replace images that are already set"
        )

    def handle(self, *args, slugs, force, **options):
        changed = install_all(force=force, slugs=slugs or None)
        self.stdout.write(f"Updated: {', '.join(changed)}" if changed else "Nothing to update.")
