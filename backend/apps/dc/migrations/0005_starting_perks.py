from django.db import migrations

# key, price, days, for_team (design/DC-FOR-PLAYERS.md, approved 2026-11-16)
PERKS = [
    ("BANNER", 50_000, 30, True),
    ("THEME", 20_000, None, True),
    ("SHOUTOUT", 10_000, 1, False),
    ("PIN", 5_000, None, False),
    ("NAME_COLOUR", 15_000, 7, False),
]


def add(apps, schema_editor):
    Perk = apps.get_model("dc", "Perk")
    for n, (key, price, days, team) in enumerate(PERKS):
        Perk.objects.get_or_create(
            key=key, defaults={"price": price, "days": days, "for_team": team, "order": n}
        )


def remove(apps, schema_editor):
    apps.get_model("dc", "Perk").objects.filter(purchases__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("dc", "0004_perks")]

    operations = [migrations.RunPython(add, remove)]
