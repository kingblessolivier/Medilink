"""Doctors, and the specialties they practise.

The distinction this app exists to draw:

    ServiceType   what a FACILITY offers        "General consultation"
    Specialty     what a CLINICIAN practises    "General medicine"
    Provider      a named person

They were conflated before, and the AI flow the brief describes - symptoms to
specialty to doctors to facilities - had nothing to route to. `Specialty` maps
to `ServiceType` so a recommendation can reach the facility search that already
exists rather than needing a parallel one.

`Provider` is deliberately NOT `StaffMember`. StaffMember is a login with a
facility scope; a doctor may have no login at all, and a receptionist is not a
doctor. Where the same person is both, link them.

Nothing here carries ratings or reviews. Those have real reputational
consequences for a named clinician and need a moderation policy before they
need a schema. See docs/11 section 3.
"""

from django.contrib.postgres.fields import ArrayField
from django.db import models

# Languages a patient might need to be seen in. Kinyarwanda first.
LANGUAGE_CHOICES = [
    ("rw", "Kinyarwanda"),
    ("en", "English"),
    ("fr", "Francais"),
    ("sw", "Kiswahili"),
]


class Specialty(models.Model):
    """A field of clinical practice.

    Populated from a fixture, not by facilities: a shared vocabulary is what
    lets the AI recommendation, the doctor directory and the facility search
    all mean the same thing by "Pediatrics".
    """

    code = models.SlugField(max_length=40, unique=True)
    name_rw = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    name_fr = models.CharField(max_length=100)
    description_en = models.TextField(blank=True)

    # The bridge to the existing facility search. A specialty with no services
    # cannot be routed to, which the fixture check reports.
    service_types = models.ManyToManyField(
        "facilities.ServiceType",
        related_name="specialties",
        blank=True,
        help_text="Facility services a clinician in this specialty delivers.",
    )

    # Whether the AI Care Guide may recommend this specialty. Some specialties
    # exist for directory completeness but are never a triage destination.
    is_triage_target = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        verbose_name_plural = "specialties"
        ordering = ["sort_order", "name_en"]

    def __str__(self) -> str:
        return self.name_en

    def name(self, language: str = "en") -> str:
        return getattr(self, f"name_{language}", self.name_en)


class Provider(models.Model):
    """A clinician, as a person - independent of where they practise."""

    class Title(models.TextChoices):
        DR = "dr", "Dr"
        PROF = "prof", "Prof"
        SISTER = "sister", "Sister"
        MR = "mr", "Mr"
        MS = "ms", "Ms"
        NONE = "", "(none)"

    slug = models.SlugField(max_length=140, unique=True)
    title = models.CharField(
        max_length=8, choices=Title.choices, blank=True, default=Title.DR
    )
    full_name = models.CharField(max_length=150)

    specialties = models.ManyToManyField(
        Specialty, related_name="providers", blank=True
    )

    # A URL rather than an upload: facilities already host staff photos, and a
    # media pipeline is a poor trade for one optional field. The UI falls back
    # to initials, which is the honest default when there is no photo.
    photo_url = models.URLField(blank=True)

    languages = ArrayField(
        models.CharField(max_length=2, choices=LANGUAGE_CHOICES),
        default=list,
        blank=True,
        help_text="Languages this clinician can consult in.",
    )

    bio_en = models.TextField(
        blank=True,
        help_text=(
            "Short professional summary. Never enter qualifications or claims "
            "that have not been verified - see docs/11 section 7."
        ),
    )

    # Set by MediLink ops once credentials have been checked with the facility.
    verified_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        indexes = [models.Index(fields=["active"], name="provider_active_idx")]

    def __str__(self) -> str:
        return self.display_name

    @property
    def display_name(self) -> str:
        return f"{self.get_title_display()} {self.full_name}".strip() if self.title else self.full_name

    @property
    def initials(self) -> str:
        """Avatar fallback. Never leaves a doctor card blank."""
        parts = [p for p in self.full_name.split() if p]
        return "".join(p[0].upper() for p in parts[:2]) or "?"

    @property
    def is_verified(self) -> bool:
        return self.verified_at is not None


class ProviderFacility(models.Model):
    """Where a provider practises.

    Many-to-many on purpose: clinicians in Rwanda commonly hold a post at a
    public hospital and consult privately elsewhere. A single FK would force
    us to pick one and hide the other from search.
    """

    provider = models.ForeignKey(
        Provider, related_name="placements", on_delete=models.CASCADE
    )
    facility = models.ForeignKey(
        "facilities.Facility", related_name="providers", on_delete=models.CASCADE
    )

    # Optional link to a login, for the minority of clinicians who use the
    # provider workspace themselves.
    staff_member = models.OneToOneField(
        "staff.StaffMember",
        null=True,
        blank=True,
        related_name="provider_placement",
        on_delete=models.SET_NULL,
    )

    role_title = models.CharField(
        max_length=80, blank=True, help_text="e.g. Consultant, Head of Paediatrics"
    )

    # Which of the facility's services this provider actually delivers. A
    # cardiologist at a hospital that also runs a dental clinic is not a
    # dentist, and booking must not offer them as one.
    service_types = models.ManyToManyField(
        "facilities.ServiceType", related_name="providers", blank=True
    )

    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "provider placements"
        unique_together = ("provider", "facility")
        ordering = ["provider__full_name"]
        indexes = [
            models.Index(fields=["facility", "active"], name="placement_facility_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.provider.display_name} at {self.facility.name}"
