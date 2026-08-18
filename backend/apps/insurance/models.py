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
