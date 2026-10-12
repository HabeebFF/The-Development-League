from celery import shared_task


@shared_task
def photo_cutout_task(player_id: int) -> bool:
    """Cut the background out of a player's new photo and frame it for their card."""
    from .models import Player
    from .photos import make_cutout

    player = Player.objects.filter(pk=player_id).first()
    return make_cutout(player) if player else False
