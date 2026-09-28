from django.db import migrations

# Map ids as written in the logs, confirmed by Habeeb on 2026-09-28.
MAPS = [
    (1, "Bermuda", "bermuda"),
    (3, "Purgatory", "purgatory"),
    (4, "Kalahari", "kalahari"),
    (22, "NeXTerra", "nexterra"),
    (29, "Solara", "solara"),
]


def seed(apps, schema_editor):
    Map = apps.get_model("maps", "Map")
    for game_map_id, name, slug in MAPS:
        Map.objects.update_or_create(slug=slug, defaults={"name": name, "game_map_id": game_map_id})


def unseed(apps, schema_editor):
    apps.get_model("maps", "Map").objects.filter(slug__in=[m[2] for m in MAPS]).delete()


class Migration(migrations.Migration):
    dependencies = [("maps", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
