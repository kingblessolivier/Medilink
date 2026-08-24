from django.db import models
from django.utils import timezone


class QueueEntry(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        CALLED = "called", "Called"
        SERVED = "served", "Served"
        LEFT = "left", "Left without being seen"
        CANCELLED = "cancelled", "Cancelled"

    OPEN_STATUSES = (Status.WAITING, Status.CALLED)

    facility = models.ForeignKey(
        "facilities.Facility", related_name="queue_entries", on_delete=models.PROTECT
    )
    service_type = models.ForeignKey(
        "facilities.ServiceType", on_delete=models.PROTECT
    )
    patient = models.ForeignKey(
        "patients.Patient",
        null=True,
        blank=True,
        related_name="queue_entries",
        on_delete=models.SET_NULL,
    )

    # Walk-in patients may have no phone and therefore no Patient record.
    walk_in_name = models.CharField(max_length=150, blank=True)

    joined_at = models.DateTimeField(default=timezone.now)
    called_at = models.DateTimeField(null=True, blank=True)
    served_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.WAITING
    )
    checked_in_by = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL
    )
    ticket_code = models.CharField(max_length=8, blank=True)
    # The local day the ticket belongs to. Stored rather than derived, because
    # the uniqueness of a ticket code is per facility, per service, PER DAY -
    # G-001 recurs every morning - and a partial index cannot be built on a
    # timezone-converted expression.
    ticket_day = models.DateField(null=True, blank=True)

    # Reception networks drop constantly. A retry after a timeout must return
    # the original entry rather than creating a duplicate.
    idempotency_key = models.CharField(max_length=64, blank=True)

    class Meta:
        verbose_name_plural = "queue entries"
        ordering = ["joined_at"]
        indexes = [
            # Drives the position COUNT - the hottest query in the system.
            models.Index(
                fields=["facility", "service_type", "status", "joined_at"],
                name="queue_position_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["facility", "idempotency_key"],
                condition=models.Q(idempotency_key__gt=""),
                name="unique_idempotency_key_per_facility",
            ),
            # Two desks checking somebody in at the same moment both counted
            # today's entries and both produced the same code. The code is
            # printed on the patient's slip and called across the waiting
            # room, so a duplicate is a real mix-up. The database decides who
            # gets it; the loser recounts. See services._create_with_unique_ticket.
            models.UniqueConstraint(
                fields=["facility", "service_type", "ticket_day", "ticket_code"],
                condition=models.Q(ticket_day__isnull=False),
                name="unique_ticket_code_per_day",
            ),
        ]

    def __str__(self) -> str:
        who = self.patient or self.walk_in_name or "unknown"
        return f"{self.ticket_code or self.pk} - {who} ({self.status})"

    @property
    def display_name(self) -> str:
        if self.patient_id and self.patient:
            return self.patient.full_name or self.patient.phone
        return self.walk_in_name or "Walk-in"

    def position(self) -> int:
        """Live position. Computed, never stored.

        A stored position column goes stale the instant anyone is served and
        forces a rewrite of every row in the queue.
        """
        if self.status != self.Status.WAITING:
            return 0
        ahead = QueueEntry.objects.filter(
            facility_id=self.facility_id,
            service_type_id=self.service_type_id,
            status=self.Status.WAITING,
            joined_at__lt=self.joined_at,
        ).count()
        return ahead + 1

    def waited_minutes(self, now=None) -> int:
        end = self.served_at or self.called_at or (now or timezone.now())
        return max(0, int((end - self.joined_at).total_seconds() // 60))


class ServiceTimeStat(models.Model):
    """How fast this service clears patients, per hour of day.

    **This is a RATE, not a wait.** The field is the median gap between one
    patient being served and the next - minutes per patient - because that is
    the only quantity the ETA formula can use: `people_ahead x rate`.

    It used to store `served_at - joined_at`, which is a patient's entire wait
    including the queue in front of them. Multiplying a queue-length-dependent
    quantity by queue length compounds, so the estimate ran roughly nine times
    high on a busy clinic and got worse the busier it was. The name said
    "service time" and the value was a latency; the field name now says which
    of the two it is, because that confusion is the whole bug.

    Inter-departure rather than `served_at - called_at` (the consultation
    itself): where two clinicians run one service in parallel the gap between
    departures correctly halves, and a consultation duration does not.

    Median, not mean: one patient who takes ninety minutes must not drag the
    estimate for everyone behind them.
    """

    facility = models.ForeignKey("facilities.Facility", on_delete=models.CASCADE)
    service_type = models.ForeignKey(
        "facilities.ServiceType", on_delete=models.CASCADE
    )
    hour_of_day = models.SmallIntegerField()
    median_minutes_per_patient = models.FloatField()
    sample_size = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("facility", "service_type", "hour_of_day")

    def __str__(self) -> str:
        return (
            f"{self.facility.name} {self.service_type.code} @{self.hour_of_day}h: "
            f"{self.median_minutes_per_patient:.0f} min/patient "
            f"(n={self.sample_size})"
        )
