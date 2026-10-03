from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rotations", "0004_replay_object_dinoculars"),
    ]

    operations = [
        migrations.AddField(
            model_name="teamrotation",
            name="path",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="The team's real route from the replay: pieces of [x, z] in world decimetres",
            ),
        ),
    ]
