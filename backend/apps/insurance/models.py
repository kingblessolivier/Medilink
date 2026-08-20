from django.db import models


class Insurer(models.Model):
    code = models.SlugField(max_length=30, unique=True)  # mutuelle, rssb, mmi
    name = models.CharField(max_length=120)
    is_public = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class FacilityInsurer(models.Model):
    """Facility-declared acceptance. This is level-1 eligibility only.

    Level 1: does this facility accept Mutuelle at all?  <- what we ship
    Level 2: is THIS patient currently covered?          <- needs RSSB integration

    The UI must never imply level 2. Copy reads "Accepts Mutuelle de Sante",
    never "You are covered".
    """

    facility = models.ForeignKey(
        "facilities.Facility", related_name="insurers", on_delete=models.CASCADE
    )
    insurer = models.ForeignKey(Insurer, on_delete=models.PROTECT)
    note = models.CharField(max_length=200, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("facility", "insurer")
        ordering = ["insurer__sort_order"]

    def __str__(self) -> str:
        return f"{self.facility.name} accepts {self.insurer.name}"


class FacilityServiceInsurer(models.Model):
    """Whether one insurer covers one service at one facility.

    This is level-1.5 eligibility, and the distinction matters:

        FacilityInsurer         "this facility accepts Mutuelle at all"
        FacilityServiceInsurer  "Mutuelle covers dental HERE"
        (not modelled)          "YOUR Mutuelle cover is currently active"

    `coverage` defaults to UNKNOWN and the UI says "Not confirmed" until a
    facility states otherwise. This is deliberate: a patient turned away at a
    counter because we implied coverage is a real harm, and an optimistic
    default would produce exactly that. Absence of data is not evidence of
    coverage.

    Nothing here records a price. We have no verified cost data, and a wrong
    number would be worse than no number.
    """

    class Coverage(models.TextChoices):
        FULL = "full", "Fully covered"
        PARTIAL = "partial", "Partially covered"
        NOT_COVERED = "not_covered", "Not covered"
        UNKNOWN = "unknown", "Not confirmed"

    facility_service = models.ForeignKey(
        "facilities.FacilityService",
        related_name="insurer_coverage",
        on_delete=models.CASCADE,
    )
    insurer = models.ForeignKey(Insurer, on_delete=models.PROTECT)
    coverage = models.CharField(
        max_length=12, choices=Coverage.choices, default=Coverage.UNKNOWN
    )
    note = models.CharField(
        max_length=200,
        blank=True,
        help_text="Any condition the facility stated, e.g. 'referral required'.",
    )
    # Set when a human confirmed this with the facility. An unconfirmed row is
    # treated as UNKNOWN however it is set.
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("facility_service", "insurer")
        ordering = ["insurer__sort_order"]

    def __str__(self) -> str:
        return (
            f"{self.facility_service} / {self.insurer.name}: "
            f"{self.get_coverage_display()}"
        )

    @property
    def effective_coverage(self) -> str:
        """Unconfirmed rows read as UNKNOWN regardless of what was entered.

        Somebody part-way through entering data must not accidentally publish
        a coverage claim.
        """
        if self.confirmed_at is None:
            return self.Coverage.UNKNOWN
        return self.coverage
