from django.contrib.gis.db import models
from django.utils import timezone


class ServiceType(models.Model):
    """General consultation, maternity, dental, laboratory, and so on."""

    code = models.SlugField(max_length=40, unique=True)
    name_en = models.CharField(max_length=100)
    name_rw = models.CharField(max_length=100)
    name_fr = models.CharField(max_length=100)
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "name_en"]

    def __str__(self) -> str:
        return self.name_en


class Facility(models.Model):
    class Ownership(models.TextChoices):
        PUBLIC = "public", "Public"
        PRIVATE = "private", "Private"
        FAITH_BASED = "faith_based", "Faith-based"

    class Level(models.TextChoices):
        HEALTH_POST = "health_post", "Health post"
        HEALTH_CENTRE = "health_centre", "Health centre"
        DISTRICT_HOSPITAL = "district_hospital", "District hospital"
        REFERRAL_HOSPITAL = "referral_hospital", "Referral hospital"
        CLINIC = "clinic", "Clinic / polyclinic"
        PHARMACY = "pharmacy", "Pharmacy"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    ownership = models.CharField(max_length=20, choices=Ownership.choices)
    level = models.CharField(max_length=24, choices=Level.choices)

    province = models.CharField(max_length=50, blank=True)
    district = models.CharField(max_length=50)
    sector = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=255, blank=True)

    # geography=True so that distance_lte and Distance() work in real metres.
    # With a plain geometry field in SRID 4326 they would work in degrees, and
    # a radius of 5000 would silently mean the whole planet.
    location = models.PointField(geography=True, srid=4326)

    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    # Only verified facilities appear in patient-facing search.
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_facilities",
    )
    verification_note = models.TextField(blank=True)

    # True once the facility runs our reception tool, i.e. live queue data
    # exists. Phase 0 leaves this False everywhere, so every wait reads
    # "not_reported" rather than an invented number.
    reports_queue = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "facilities"
        ordering = ["name"]
        indexes = [
            # Explicit names so hand-written migrations stay in sync with
            # makemigrations --check in CI.
            models.Index(fields=["district"], name="facility_district_idx"),
            models.Index(fields=["verified_at"], name="facility_verified_idx"),
            # The GIST index on `location` is created in migration 0002.
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.district})"

    @property
    def is_verified(self) -> bool:
        return self.verified_at is not None

    def mark_verified(self, user=None, note: str = "") -> None:
        self.verified_at = timezone.now()
        self.verified_by = user
        if note:
            self.verification_note = note
        self.save(update_fields=["verified_at", "verified_by", "verification_note"])


class FacilityService(models.Model):
    facility = models.ForeignKey(
        Facility, related_name="services", on_delete=models.CASCADE
    )
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT)
    available = models.BooleanField(default=True)

    class Meta:
        unique_together = ("facility", "service_type")

    def __str__(self) -> str:
        return f"{self.facility.name} - {self.service_type.name_en}"


class OpeningHours(models.Model):
    """One row per continuous open period.

    Two rows for the same weekday model a lunch break. A facility open around
    the clock has one row per day of 00:00 to 23:59.
    """

    WEEKDAYS = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    facility = models.ForeignKey(
        Facility, related_name="opening_hours", on_delete=models.CASCADE
    )
    weekday = models.SmallIntegerField(choices=WEEKDAYS)
    opens_at = models.TimeField()
    closes_at = models.TimeField()

    class Meta:
        verbose_name_plural = "opening hours"
        unique_together = ("facility", "weekday", "opens_at")
        ordering = ["weekday", "opens_at"]

    def __str__(self) -> str:
        return f"{self.get_weekday_display()} {self.opens_at}-{self.closes_at}"
