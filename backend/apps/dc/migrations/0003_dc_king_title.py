from django.db import migrations


def add(apps, schema_editor):
    CardDesign = apps.get_model("shop", "CardDesign")
    CardDesign.objects.get_or_create(
        slug="title-dc-king",
        defaults={
            "name": "DC King",
            "kind": "TITLE",
            "rarity": "LEGENDARY",
            "price": 0,
            "parts": {"palette": "gold", "pattern": "none", "effect": "none"},
            "unlock": "dcking:1",
            "players_only": True,
            "order": 199,
        },
    )


def remove(apps, schema_editor):
    apps.get_model("shop", "CardDesign").objects.filter(
        slug="title-dc-king", owners__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("dc", "0002_ranks_and_dc_king"),
        ("shop", "0004_player_shop_items"),
    ]

    operations = [migrations.RunPython(add, remove)]
