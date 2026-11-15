from django.apps import AppConfig


class TournamentsConfig(AppConfig):
    name = "apps.tournaments"
    label = "tournaments"
    verbose_name = "Tournaments"

    def ready(self) -> None:
        from . import signals  # noqa: F401
