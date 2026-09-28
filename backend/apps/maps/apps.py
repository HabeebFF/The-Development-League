from django.apps import AppConfig
from django.db.models.signals import post_migrate


class MapsConfig(AppConfig):
    name = "apps.maps"
    label = "maps"

    def ready(self):
        from .bundled import install_missing

        post_migrate.connect(install_missing, sender=self)
