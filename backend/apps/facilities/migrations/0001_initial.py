import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.conf import settings
from django.contrib.postgres.operations import CreateExtension
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Must run before any geography column is created.
        CreateExtension("postgis"),
        migrations.CreateModel(
            name="ServiceType",
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
                ("code", models.SlugField(max_length=40, unique=True)),
                ("name_en", models.CharField(max_length=100)),
                ("name_rw", models.CharField(max_length=100)),
                ("name_fr", models.CharField(max_length=100)),
                ("sort_order", models.PositiveSmallIntegerField(default=100)),
            ],
            options={"ordering": ["sort_order", "name_en"]},
        ),
        migrations.CreateModel(
            name="Facility",
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
                ("name", models.CharField(max_length=200)),
                ("slug", models.SlugField(max_length=220, unique=True)),
                (
                    "ownership",
                    models.CharField(
                        choices=[
                            ("public", "Public"),
                            ("private", "Private"),
                            ("faith_based", "Faith-based"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "level",
                    models.CharField(
                        choices=[
                            ("health_post", "Health post"),
                            ("health_centre", "Health centre"),
                            ("district_hospital", "District hospital"),
                            ("referral_hospital", "Referral hospital"),
                            ("clinic", "Clinic / polyclinic"),
                            ("pharmacy", "Pharmacy"),
                        ],
                        max_length=24,
                    ),
                ),
                ("province", models.CharField(blank=True, max_length=50)),
                ("district", models.CharField(max_length=50)),
                ("sector", models.CharField(blank=True, max_length=50)),
                ("address", models.CharField(blank=True, max_length=255)),
                (
                    "location",
                    django.contrib.gis.db.models.fields.PointField(
                        geography=True, srid=4326
                    ),
                ),
                ("phone", models.CharField(blank=True, max_length=20)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("verification_note", models.TextField(blank=True)),
                ("reports_queue", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "verified_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="verified_facilities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"verbose_name_plural": "facilities", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="OpeningHours",
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
                (
                    "weekday",
                    models.SmallIntegerField(
                        choices=[
                            (0, "Monday"),
                            (1, "Tuesday"),
                            (2, "Wednesday"),
                            (3, "Thursday"),
                            (4, "Friday"),
                            (5, "Saturday"),
                            (6, "Sunday"),
                        ]
                    ),
                ),
                ("opens_at", models.TimeField()),
                ("closes_at", models.TimeField()),
                (
                    "facility",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="opening_hours",
                        to="facilities.facility",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "opening hours",
                "ordering": ["weekday", "opens_at"],
                "unique_together": {("facility", "weekday", "opens_at")},
            },
        ),
        migrations.CreateModel(
            name="FacilityService",
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
                ("available", models.BooleanField(default=True)),
                (
                    "facility",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="services",
                        to="facilities.facility",
                    ),
                ),
                (
                    "service_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="facilities.servicetype",
                    ),
                ),
            ],
            options={"unique_together": {("facility", "service_type")}},
        ),
        migrations.AddIndex(
            model_name="facility",
            index=models.Index(fields=["district"], name="facility_district_idx"),
        ),
        migrations.AddIndex(
            model_name="facility",
            index=models.Index(fields=["verified_at"], name="facility_verified_idx"),
        ),
    ]
