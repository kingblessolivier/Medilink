import hashlib

import phonenumbers
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError

RWANDA_REGION = "RW"


def normalise_phone(raw: str) -> str:
    """Return E.164, or raise ValidationError.

    Phone number is identity in this system - one patient may arrive from the
    PWA, USSD and WhatsApp, and all three must resolve to the same row. Never
    trust client formatting; normalise on every write.
    """
    if not raw:
        raise ValidationError("Phone number is required.")
    try:
        parsed = phonenumbers.parse(raw, RWANDA_REGION)
    except phonenumbers.NumberParseException as exc:
        raise ValidationError("Could not read that phone number.") from exc

    if not phonenumbers.is_valid_number(parsed):
        raise ValidationError("That is not a valid phone number.")

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def hash_national_id(value: str) -> str:
    """SHA-256 with a server-side pepper.

    We never need to know a patient's ID number, only whether two records are
    the same person. The pepper lives in the environment, never in the
    database, so a database dump alone does not allow brute-forcing the short,
    structured ID space. Rotating it invalidates every stored hash - treat that
    as a migration, not a config edit. See docs/08.
    """
    digits = "".join(ch for ch in value if ch.isdigit())
    pepper = getattr(settings, "NATIONAL_ID_PEPPER", "")
    return hashlib.sha256((pepper + digits).encode()).hexdigest()


class Patient(models.Model):
    class Language(models.TextChoices):
        RW = "rw", "Kinyarwanda"
        EN = "en", "English"
        FR = "fr", "Francais"

    phone = models.CharField(max_length=20, unique=True)

    # Web sign-in. Blank for the many patients who only ever reach MediLink
    # through USSD or WhatsApp - those channels identify a caller by the phone
    # number the aggregator hands us, and a feature phone will never hold a
    # password. See apps/accounts/README.md.
    #
    # Uniqueness is enforced across BOTH this column and auth.User at
    # registration: the login endpoint tries staff before patients, so a
    # patient allowed to take a staff username could never sign in again.
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    password = models.CharField(max_length=128, blank=True)

    full_name = models.CharField(max_length=150, blank=True)
    language = models.CharField(
        max_length=2, choices=Language.choices, default=Language.RW
    )
    insurer = models.ForeignKey(
        "insurance.Insurer", null=True, blank=True, on_delete=models.SET_NULL
    )
    # Set on the first USSD session so returning callers skip the district
    # screen entirely - one step saved on every future session, and USSD
    # sessions are billed per step.
    district = models.CharField(max_length=50, blank=True)
    national_id_hash = models.CharField(max_length=64, blank=True)
    home_location = models.PointField(geography=True, null=True, blank=True)

    # Rwanda Law 058/2021 requires consent to be captured and recorded, with a
    # timestamp and against a specific version of what was agreed to. Null for
    # every patient created before web registration existed - USSD and
    # WhatsApp callers among them - and null is the honest value: nobody
    # collected it, and backfilling a timestamp would be manufacturing a
    # record of something that did not happen.
    consented_at = models.DateTimeField(null=True, blank=True)
    # The privacy notice version agreed to. A later revision does not
    # retroactively become what somebody consented to.
    consent_version = models.CharField(max_length=20, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    @property
    def has_consented(self) -> bool:
        return self.consented_at is not None

    def set_password(self, raw_password: str) -> None:
        """Hash with Django's configured hasher - never store the raw value."""
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        if not self.password:
            return False
        return check_password(raw_password, self.password)

    class Meta:
        indexes = [models.Index(fields=["phone"], name="patient_phone_idx")]

    def __str__(self) -> str:
        return self.full_name or self.phone

    @classmethod
    def get_or_create_by_phone(cls, raw_phone: str, **defaults):
        return cls.objects.get_or_create(
            phone=normalise_phone(raw_phone), defaults=defaults
        )


class OTPCode(models.Model):
    """A one-time sign-in code.

    Only the hash is stored, so a database dump does not hand over live codes.
    """

    phone = models.CharField(max_length=20)
    code_hash = models.CharField(max_length=64)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["phone", "consumed_at"], name="otp_phone_open_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"OTP for {self.phone} ({'used' if self.consumed_at else 'open'})"


class PatientAccessLog(models.Model):
    """Who looked at whose record, and when.

    docs/08 section 6: every read and write of an identifiable patient record
    must be attributable. This table is what surfaces the anomaly that matters -
    a receptionist viewing hundreds of records outside their shift.

    `patient` is nullable because a queue board is a BULK read: one row records
    that a staff member listed N patients at once, rather than N rows. Logging
    each would drown the signal in noise, and the board is rendered constantly.
    """

    class Action(models.TextChoices):
        BOARD = "board", "Viewed queue board"
        VIEW = "view", "Viewed a patient record"
        CHECK_IN = "check_in", "Checked a patient in"
        TRANSITION = "transition", "Changed a queue entry"
        UPDATE = "update", "Updated a patient record"
        EXPORT = "export", "Exported own data"
        ERASE = "erase", "Erased own data"

    actor = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL
    )
    # Set when the patient acted on their own record rather than a staff member.
    acting_patient = models.ForeignKey(
        "patients.Patient",
        null=True,
        blank=True,
        related_name="own_access_logs",
        on_delete=models.SET_NULL,
    )
    patient = models.ForeignKey(
        Patient,
        null=True,
        blank=True,
        related_name="access_logs",
        on_delete=models.SET_NULL,
    )
    facility = models.ForeignKey(
        "facilities.Facility", null=True, blank=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=12, choices=Action.choices)
    record_count = models.PositiveIntegerField(default=1)
    occurred_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["actor", "occurred_at"], name="access_actor_idx"),
            models.Index(fields=["patient", "occurred_at"], name="access_patient_idx"),
        ]

    def __str__(self) -> str:
        who = self.actor or self.acting_patient or "anonymous"
        return f"{who} {self.action} ({self.record_count}) at {self.occurred_at}"
