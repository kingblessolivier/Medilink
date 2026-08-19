from django.db import models


class StaffMember(models.Model):
    """Links a Django user to exactly one facility.

    Every provider-side query is scoped through this. A receptionist at one
    clinic must never be able to read another clinic's patients - that is the
    breach that ends the project. Enforcement lives in
    apps.staff.permissions.FacilityScopedMixin, never in individual views.
    """

    class Role(models.TextChoices):
        RECEPTIONIST = "receptionist", "Receptionist"
        ADMIN = "admin", "Facility administrator"
        CLINICIAN = "clinician", "Clinician"

    user = models.OneToOneField(
        "auth.User", on_delete=models.CASCADE, related_name="staffmember"
    )
    facility = models.ForeignKey(
        "facilities.Facility", related_name="staff", on_delete=models.CASCADE
    )
    role = models.CharField(max_length=14, choices=Role.choices)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user.username} - {self.facility.name} ({self.role})"

    @property
    def can_manage_queue(self) -> bool:
        return self.role in {self.Role.RECEPTIONIST, self.Role.ADMIN}
