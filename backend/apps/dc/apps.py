from django.apps import AppConfig


class DcConfig(AppConfig):
    name = "apps.dc"
    label = "dc"
    verbose_name = "DC for players"

    def ready(self):
        from . import signals  # noqa: F401
