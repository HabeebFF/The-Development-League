"""Open automatic markets that close right at 8PM or 10PM (Lagos) now close a minute
earlier, at 7:59 and 9:59, like the ones made from now on."""

import datetime as dt
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import migrations

STARTS = {20, 22}


def forwards(apps, schema_editor):
    AutoMarket = apps.get_model("predictions", "AutoMarket")
    tz = ZoneInfo(settings.ANALYTICS_TIME_ZONE)
    for row in AutoMarket.objects.select_related("market").filter(
        market__status__in=["OPEN", "SUSPENDED", "DRAFT"]
    ):
        m = row.market
        local = m.closes_at.astimezone(tz)
        if local.hour in STARTS and local.minute == 0 and local.second == 0:
            m.closes_at -= dt.timedelta(minutes=1)
            m.save(update_fields=["closes_at"])


class Migration(migrations.Migration):
    dependencies = [("predictions", "0010_dc_label")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
