import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [("facilities", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Insurer",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code", models.SlugField(max_length=30, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("is_public", models.BooleanField(default=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=100)),
            ],
            options={"ordering": ["sort_order", "name"]},
        ),
        migrations.CreateModel(
            name="FacilityInsurer",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("note", models.CharField(blank=True, max_length=200)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "facility",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="insurers",
                        to="facilities.facility",
                    ),
                ),
                (
                    "insurer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="insurance.insurer",
                    ),
                ),
            ],
            options={
                "ordering": ["insurer__sort_order"],
                "unique_together": {("facility", "insurer")},
            },
        ),
    ]
