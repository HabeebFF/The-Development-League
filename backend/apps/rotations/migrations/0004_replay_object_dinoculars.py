from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rotations", "0003_replay_object"),
    ]

    operations = [
        migrations.AlterField(
            model_name="replayobject",
            name="kind",
            field=models.CharField(
                choices=[
                    ("PLAYER_UAV", "Player UAV"),
                    ("GENERAL_UAV", "General UAV"),
                    ("BOLT_MAKER", "Bolt Maker"),
                    ("DINOCULARS", "Dinoculars"),
                ],
                max_length=16,
            ),
        ),
    ]
