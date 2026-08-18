from django.db import migrations


class Migration(migrations.Migration):
    """The spatial index. Do not skip this.

    PointField alone does not create the index that makes ST_DWithin fast.
    Without it every nearby search is a sequential scan of the whole table,
    and the p95 target in docs/04 is unreachable.

    Verify with:
        EXPLAIN ANALYZE
        SELECT id FROM facilities_facility
        WHERE ST_DWithin(location, ST_MakePoint(30.0606, -1.9536)::geography, 5000);

    The plan must show "Index Scan using facility_location_gist".
    """

    dependencies = [("facilities", "0001_initial")]

    operations = [
        migrations.RunSQL(
            sql=(
                "CREATE INDEX IF NOT EXISTS facility_location_gist "
                "ON facilities_facility USING GIST (location);"
            ),
            reverse_sql="DROP INDEX IF EXISTS facility_location_gist;",
        ),
    ]
