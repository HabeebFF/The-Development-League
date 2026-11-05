"""Game UIDs now link at sign-up. Link the ones still waiting for staff, the same way, unless
another account already has that UID (those stay for staff)."""

from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    PlayerClaim = apps.get_model("accounts", "PlayerClaim")
    Player = apps.get_model("league", "Player")
    for claim in PlayerClaim.objects.filter(status="PENDING").select_related("user"):
        player = Player.objects.filter(game_uid=claim.game_uid).first()
        if player and player.user_id and player.user_id != claim.user_id:
            continue
        Player.objects.filter(user=claim.user).exclude(game_uid=claim.game_uid).update(user=None)
        if player is None:
            name = claim.user.display_name or claim.user.email.split("@")[0]
            player = Player(
                game_uid=claim.game_uid,
                current_name_raw=name,
                display_name=name,
                search_name=name.casefold(),
            )
        player.user = claim.user
        player.save()
        claim.status = "APPROVED"
        claim.reviewed_at = timezone.now()
        claim.save(update_fields=["status", "reviewed_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_seed_plans_and_features"),
        ("league", "0008_team_igl"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
