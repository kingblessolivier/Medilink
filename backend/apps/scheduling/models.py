import secrets

from django.db import models

# Unambiguous over a phone line and on a paper slip: no O/0, no I/1.
REFERENCE_ALPHABET = "ACDEFGHJKLMNPQRSTUVWXY3456789"
REFERENCE_LENGTH = 6


def new_reference() -> str:
    return "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(REFERENCE_LENGTH))


class ScheduleTemplate(models.Model):
    """Recurring weekly capacity, from which bookable slots are generated.

    Slots are never materialised as rows. A facility open six days a week for a
    year is roughly 15,000 slot rows that mostly stay empty; expanding the
    template on read is cheaper and cannot drift from the template.
    """

    facility = models.ForeignKey(
        "facilities.Facility",
        related_name="schedule_templates",
        on_delete=models.CASCADE,
    )
    service_type = models.ForeignKey(
        "facilities.ServiceType", on_delete=models.PROTECT
    )
    weekday = models.SmallIntegerField(choices=[(i, i) for i in range(7)])
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_minutes = models.PositiveSmallIntegerField(default=15)
    capacity_per_slot = models.PositiveSmallIntegerField(default=1)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["weekday", "start_time"]
        unique_together = ("facility", "service_type", "weekday", "start_time")

    def __str__(self) -> str:
        return (
            f"{self.facility.name} {self.service_type.code} "
            f"day {self.weekday} {self.start_time}-{self.end_time}"
        )


class Appointment(models.Model):
    class Status(models.TextChoices):
        BOOKED = "booked", "Booked"
        ARRIVED = "arrived", "Arrived"
        SERVED = "served", "Served"
        NO_SHOW = "no_show", "No show"
        CANCELLED = "cancelled", "Cancelled"

    OPEN_STATUSES = (Status.BOOKED, Status.ARRIVED)

    class BookedVia(models.TextChoices):
        APP = "app", "App"
        USSD = "ussd", "USSD"
        WHATSAPP = "whatsapp", "WhatsApp"
        DESK = "desk", "Reception desk"

    facility = models.ForeignKey(
        "facilities.Facility", related_name="appointments", on_delete=models.PROTECT
    )
    patient = models.ForeignKey(
        "patients.Patient", related_name="appointments", on_delete=models.PROTECT
    )
    service_type = models.ForeignKey(
        "facilities.ServiceType", on_delete=models.PROTECT
    )

    slot_start = models.DateTimeField()
    slot_end = models.DateTimeField()
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.BOOKED
    )
    booked_via = models.CharField(
        max_length=12, choices=BookedVia.choices, default=BookedVia.APP
    )
    reference = models.CharField(max_length=8, unique=True, default=new_reference)

    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["slot_start"]
        indexes = [
            models.Index(
                fields=["facility", "slot_start"], name="appointment_facility_idx"
            ),
            models.Index(
                fields=["patient", "slot_start"], name="appointment_patient_idx"
            ),
        ]
        constraints = [
            # Two taps on the last slot must not both succeed.
            models.UniqueConstraint(
                fields=["patient", "facility", "slot_start"],
                condition=models.Q(status__in=["booked", "arrived"]),
                name="one_active_appointment_per_slot",
            )
        ]

    def __str__(self) -> str:
        return f"{self.reference} {self.patient} @ {self.slot_start:%Y-%m-%d %H:%M}"
