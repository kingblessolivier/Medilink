from rest_framework import serializers

from apps.patients.models import normalise_phone


class LoginSerializer(serializers.Serializer):
    # Not an EmailField and not a phone field: this accepts a staff username,
    # a patient username, or a patient's phone number. Which one it is gets
    # decided in services.sign_in, not here.
    username = serializers.CharField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class RegisterSerializer(serializers.Serializer):
    username = serializers.RegexField(
        # Letters, digits, dot, dash, underscore. No spaces and no '@', so a
        # username can never be mistaken for an email address, and no '+' so
        # it cannot be mistaken for a phone number either.
        r"^[A-Za-z0-9._-]{3,150}$",
        error_messages={
            "invalid": (
                "Use 3 or more letters, numbers, dots, dashes or underscores."
            )
        },
    )
    password = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False)
    phone = serializers.CharField(max_length=20)
    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    # Required, and required to be TRUE. A checkbox that can be sent as false
    # and still register somebody is not consent, it is decoration.
    # Rwanda Law 058/2021; docs/08 section 6.
    consent = serializers.BooleanField()

    def validate_consent(self, value):
        if value is not True:
            raise serializers.ValidationError(
                "You must agree to the privacy notice to create an account."
            )
        return value

    def validate_phone(self, value):
        try:
            return normalise_phone(value)
        except Exception:  # noqa: BLE001
            raise serializers.ValidationError("Enter a valid Rwandan phone number.") from None

    def validate_password(self, value):
        # A deliberately light rule. Long-and-memorable beats short-and-clever,
        # and a composition rule pushes people toward "Password1!" and a
        # sticky note on the reception desk.
        if value.strip() == "":
            raise serializers.ValidationError("Enter a password.")
        return value


class SessionFacilitySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    name = serializers.CharField()
    district = serializers.CharField()


class SessionSerializer(serializers.Serializer):
    # Null when the caller authenticated but is neither a patient, active
    # facility staff, nor a superuser. The client shows an explanation rather
    # than looping them back to a form that will keep succeeding.
    kind = serializers.CharField(allow_null=True)
    display_name = serializers.CharField(allow_blank=True)
    username = serializers.CharField(allow_blank=True)
    facility = SessionFacilitySerializer(allow_null=True)
    can_manage_queue = serializers.BooleanField()


class SignInResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    session = SessionSerializer()
