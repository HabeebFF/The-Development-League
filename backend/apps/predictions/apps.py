from django.apps import AppConfig


class PredictionsConfig(AppConfig):
    name = "apps.predictions"
    label = "predictions"
    verbose_name = "Predictions (virtual coins)"

    def ready(self):
        from apps.scrims.services import lobby_changed

        from .auto import follow_registration

        lobby_changed.connect(follow_registration, dispatch_uid="predictions-follow-registration")
