"""Rename the wait statistic to say that it is a rate, and drop the old values.

`median_minutes` stored `served_at - joined_at` - a patient's entire wait,
queue included - and the ETA multiplied it by the number of people ahead. The
field now stores the gap between consecutive patients being served, which is
the per-patient rate that formula actually needs.

**The existing rows are deleted rather than carried over.** Under the new
meaning every stored value is wrong, and roughly nine times too large on a busy
clinic. Renaming the column alone would keep serving those numbers, correctly
labelled, until the next refresh - and a wrong wait time is the one thing this
product must not show. Emptying the table makes every facility report
`insufficient_data` until `refresh_service_time_stats` runs (every 15 minutes
under Celery beat, or `manage.py refresh_service_stats`), which is the honest
state to be in meanwhile.

Irreversible in the sense that matters: the reverse operation restores the
column name, not the discarded values. They are recomputed from QueueEntry
either way, so nothing is actually lost.
"""

from django.db import migrations, models


def drop_stale_stats(apps, schema_editor):
    apps.get_model("queueing", "ServiceTimeStat").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [("queueing", "0001_initial")]

    operations = [
        migrations.RenameField(
            model_name="servicetimestat",
            old_name="median_minutes",
            new_name="median_minutes_per_patient",
        ),
        migrations.AlterField(
            model_name="servicetimestat",
            name="median_minutes_per_patient",
            field=models.FloatField(),
        ),
        migrations.RunPython(drop_stale_stats, migrations.RunPython.noop),
    ]
