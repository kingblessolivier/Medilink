from django.db import models


class Notification(models.Model):
    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        PUSH = "push", "Web push"

    class Kind(models.TextChoices):
        OTP = "otp", "Sign-in code"
        LEAVE_NOW = "leave_now", "Leave now"
        CALLED = "called", "You have been called"
        APPT_REMINDER_24H = "appt_reminder_24h", "Appointment reminder (24h)"
        APPT_REMINDER_2H = "appt_reminder_2h", "Appointment reminder (2h)"
        APPT_CANCELLED = "appt_cancelled", "Appointment cancelled"

    patient = models.ForeignKey(
        "patients.Patient",
        null=True,
        blank=True,
        related_name="notifications",
        on_delete=models.CASCADE,
    )
    # OTPs are sent before a Patient row necessarily exists.
    phone = models.CharField(max_length=20)

    channel = models.CharField(max_length=6, choices=Channel.choices)
    kind = models.CharField(max_length=24, choices=Kind.choices)
    body = models.TextField()

    queue_entry = models.ForeignKey(
        "queueing.QueueEntry", null=True, blank=True, on_delete=models.SET_NULL
    )
    appointment = models.ForeignKey(
        "scheduling.Appointment", null=True, blank=True, on_delete=models.SET_NULL
    )

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=255, blank=True)
    provider_ref = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # THE duplicate-SMS defence. A beat task running every minute will
            # occasionally overlap itself; the database, not application logic,
            # is what guarantees a patient gets "Leave now" exactly once.
            models.UniqueConstraint(
                fields=["queue_entry", "kind"],
                condition=models.Q(queue_entry__isnull=False),
                name="one_notification_per_kind_per_queue_entry",
            ),
            models.UniqueConstraint(
                fields=["appointment", "kind"],
                condition=models.Q(appointment__isnull=False),
                name="one_notification_per_kind_per_appointment",
            ),
        ]
        indexes = [
            models.Index(fields=["phone", "created_at"], name="notification_phone_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} to {self.phone}"
