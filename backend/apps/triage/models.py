from django.db import models


class TriageOutcome(models.Model):
    """Anonymous aggregate, for improving the protocol.

    Deliberately has NO link to a Patient, no session id, and no answers.
    Triage answers are the most sensitive data this product touches; docs/08
    requires that they stay in Redis with a short TTL and are never joined to
    an identity. What survives is enough to ask "does this protocol send too
    many people to the referral hospital?" and nothing more.

    `hour_bucket` rather than a timestamp, so a row cannot be correlated with a
    queue check-in a minute later to re-identify somebody.
    """

    protocol_version = models.CharField(max_length=20)
    recommended_service = models.CharField(max_length=40, blank=True)
    escalated_emergency = models.BooleanField(default=False)
    questions_answered = models.PositiveSmallIntegerField(default=0)
    date = models.DateField()
    hour_bucket = models.SmallIntegerField()

    class Meta:
        indexes = [
            models.Index(
                fields=["protocol_version", "date"], name="triage_version_date_idx"
            ),
        ]

    def __str__(self) -> str:
        target = "EMERGENCY" if self.escalated_emergency else self.recommended_service
        return f"{self.date} {self.protocol_version} -> {target}"
