import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Older views have no key (they can't be reported on any more); new ones get one.
        migrations.AddField(
            model_name="pageview",
            name="key",
            field=models.UUIDField(editable=False, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="pageview",
            name="key",
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="pageview",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="page_views",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="pageview",
            name="duration_s",
            field=models.PositiveIntegerField(blank=True, help_text="Time on page", null=True),
        ),
        migrations.CreateModel(
            name="Action",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("name", models.CharField(help_text='e.g. "Pressed Play", "Signed in"', max_length=80)),
                ("detail", models.CharField(blank=True, max_length=120)),
                (
                    "view",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="actions",
                        to="analytics.pageview",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
    ]
