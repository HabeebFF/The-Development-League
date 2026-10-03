"""Load the OB55 research as drafts for staff to review (see apps/coach/research.py)."""

from django.db import migrations


def load(apps, schema_editor):
    from apps.coach import research

    if research.LATEST.exists():
        research.load(
            research.read(),
            apps.get_model("coach", "KnowledgeEntry"),
            apps.get_model("maps", "Map"),
            apps.get_model("maps", "MapArea"),
        )


class Migration(migrations.Migration):
    dependencies = [("coach", "0005_review_and_sources"), ("maps", "0004_area_status")]
    operations = [migrations.RunPython(load, migrations.RunPython.noop)]
