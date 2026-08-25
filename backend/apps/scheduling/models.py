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
    # None means the facility's general clinic - "any available". A provider
    # makes this that clinician's own session. Deliberately reuses this model
    # rather than adding a parallel availability table, so slot expansion,
    # capacity locking and cancellation all work unchanged.
    provider = models.ForeignKey(
        "providers.Provider",
        null=True,
        blank=True,
        related_name="schedule_templates",
        on_delete=models.CASCADE,
    )
    weekday = models.SmallIntegerField(choices=[(i, i) for i in range(7)])
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_minutes = models.PositiveSmallIntegerField(default=15)
    capacity_per_slot = models.PositiveSmallIntegerField(default=1)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["weekday", "start_time"]
        constraints = [
            # `nulls_distinct=False` is the whole point of this constraint.
            #
            # It was `unique_together`, which in SQL compares NULL to NULL as
            # NOT EQUAL - so it protected a named clinician's list and silently
            # permitted duplicates of the general clinic, where `provider` is
            # NULL. The general clinic is the DEFAULT and by far the common
            # case, so the constraint covered everything except the thing that
            # needed covering.
            #
            # Two identical templates produce the same slot twice in
            # `available_slots`, so a patient sees 09:00 listed twice and
            # `_template_for` picks between them arbitrarily. It never
            # surfaced while only developers could create templates through
            # fixtures; it surfaced the moment a facility could.
            models.UniqueConstraint(
                fields=[
                    "facility",
                    "service_type",
                    "provider",
                    "weekday",
                    "start_time",
                ],
                nulls_distinct=False,
                name="unique_session_per_slot_start",
            )
        ]

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
        # The patient turned up and nobody recorded what happened next.
        #
        # Deliberately NOT no_show: they came, and counting it against them
        # would put a facility's own record-keeping into a number it uses to
        # judge its patients. Not `served` either - nobody said they were.
        # Its own status, excluded from the no-show rate and surfaced on the
        # reports screen, turns a silent data leak into a visible prompt to
        # close the day's records. See notifications.tasks.close_stale.
        UNRECORDED = "unrecorded", "Arrived, outcome not recorded"

    OPEN_STATUSES = (Status.BOOKED, Status.ARRIVED)

    class BookedVia(models.TextChoices):
        APP = "app", "App"
        USSD = "ussd", "USSD"
        WHATSAPP = "whatsapp", "WhatsApp"
        DESK = "desk", "Reception desk"

    facility = models.ForeignKey(
        "facilities.Facility", related_name="appointments", on_delete=models.PROTECT
    )
    # Nullable so a patient can exercise their right to erasure without the
    # facility losing its no-show counts. See apps/patients/privacy.py.
    patient = models.ForeignKey(
        "patients.Patient",
        related_name="appointments",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    service_type = models.ForeignKey(
        "facilities.ServiceType", on_delete=models.PROTECT
    )
    # None means the patient chose "any available", which stays the default:
    # naming a doctor narrows availability and most patients do not need to.
    provider = models.ForeignKey(
        "providers.Provider",
        null=True,
        blank=True,
        related_name="appointments",
        on_delete=models.SET_NULL,
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
