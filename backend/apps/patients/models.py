import hashlib

import phonenumbers
from django.conf import settings
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
    full_name = models.CharField(max_length=150, blank=True)
    language = models.CharField(
        max_length=2, choices=Language.choices, default=Language.RW
    )
    insurer = models.ForeignKey(
        "insurance.Insurer", null=True, blank=True, on_delete=models.SET_NULL
    )
    national_id_hash = models.CharField(max_length=64, blank=True)
    home_location = models.PointField(geography=True, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["phone"], name="patient_phone_idx")]

    def __str__(self) -> str:
        return self.full_name or self.phone

    @classmethod
    def get_or_create_by_phone(cls, raw_phone: str, **defaults):
        return cls.objects.get_or_create(
            phone=normalise_phone(raw_phone), defaults=defaults
        )
