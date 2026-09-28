from django.db import migrations

DEFAULT_RULE = "TDL default"
PLACEMENT_POINTS = {
    "1": 12,
    "2": 9,
    "3": 8,
    "4": 7,
    "5": 6,
    "6": 5,
    "7": 4,
    "8": 3,
    "9": 2,
    "10": 1,
}


def seed(apps, schema_editor):
    apps.get_model("league", "ScoringRule").objects.get_or_create(
        name=DEFAULT_RULE,
        defaults={"placement_points": PLACEMENT_POINTS, "default_points": 0, "points_per_kill": 1},
    )


def unseed(apps, schema_editor):
    apps.get_model("league", "ScoringRule").objects.filter(
        name=DEFAULT_RULE, seasons__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("league", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
