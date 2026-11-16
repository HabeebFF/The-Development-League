from django.db.models.signals import pre_delete
from django.dispatch import receiver

from apps.league.models import Match


@receiver(pre_delete, sender=Match)
def take_back_rewards(sender, instance: Match, **kwargs):
    """A deleted match pays nothing: take back its DC before its rewards are deleted."""
    from .rewards import enabled, take_back_match

    if enabled():
        take_back_match(instance)
