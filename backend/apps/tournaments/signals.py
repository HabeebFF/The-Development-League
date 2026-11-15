"""Held prizes land as soon as the winner's game UID is linked to a site account."""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.league.models import Player


@receiver(post_save, sender=Player)
def pay_held_prizes(sender, instance: Player, **kwargs) -> None:
    if instance.user_id is None:
        return
    from .models import PrizePayout

    if PrizePayout.objects.filter(player=instance, paid_at__isnull=True).exists():
        from .services import pay_held

        transaction.on_commit(lambda: pay_held(instance.pk))
