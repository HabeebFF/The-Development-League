"""Starter entries for the knowledge base. Numbers here were measured from our own replay
files (see the live replay work); staff write the rest."""

from django.db import migrations

STARTER = [
    ("UTILITY", "Gloo Wall", "", {}),
    (
        "UTILITY",
        "UAV",
        "",
        {"scan_radius_m": {"player_uav": 65, "general_uav": 100}},
    ),
    (
        "UTILITY",
        "Bolt Maker",
        "",
        {"duration_s": 30, "strikes": 30, "damage_per_strike": 60, "max_per_match": 5},
    ),
    ("UTILITY", "Dinoculars", "", {"scan_radius_m": 50, "max_per_player": 7}),
    ("ZONE", "How the zone closes", "", {}),
]


def add(apps, schema_editor):
    KnowledgeEntry = apps.get_model("coach", "KnowledgeEntry")
    for kind, title, body, data in STARTER:
        KnowledgeEntry.objects.get_or_create(
            kind=kind, title=title, map=None, defaults={"body": body, "data": data}
        )


class Migration(migrations.Migration):
    dependencies = [("coach", "0001_initial")]
    operations = [migrations.RunPython(add, migrations.RunPython.noop)]
