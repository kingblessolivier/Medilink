from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import QueueEntry


class CheckInSerializer(serializers.Serializer):
    """Minimal on purpose.

    Target is under 10 seconds of human time per check-in, so the payload is a
    service plus one identifier. `facility` is never accepted from the client -
    it is derived from the authenticated staff member, so a receptionist cannot
    check a patient into another facility.
    """

    service = serializers.SlugField()
    phone = serializers.CharField(required=False, allow_blank=True)
    walk_in_name = serializers.CharField(
        required=False, allow_blank=True, max_length=150
    )
    # Offline sync replays the receptionist's own timestamp.
    client_recorded_at = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        if not attrs.get("phone") and not attrs.get("walk_in_name"):
            raise serializers.ValidationError(
                {"phone": "Provide a phone number, or a name for a walk-in."}
            )
        return attrs


class QueueEntrySerializer(serializers.ModelSerializer):
    """Staff-facing view of one entry."""

    display_name = serializers.SerializerMethodField()
    service = serializers.CharField(source="service_type.code", read_only=True)
    phone = serializers.SerializerMethodField()
    position = serializers.SerializerMethodField()
    waited_minutes = serializers.SerializerMethodField()

    # Declared read-only so the OpenAPI schema marks them as always present in
    # a response. Model fields with defaults are otherwise emitted as optional,
    # which forces every client into needless undefined checks.
    id = serializers.IntegerField(read_only=True)
    ticket_code = serializers.CharField(read_only=True)
    status = serializers.ChoiceField(
        choices=QueueEntry.Status.choices, read_only=True
    )
    joined_at = serializers.DateTimeField(read_only=True)
    called_at = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta:
        model = QueueEntry
        fields = [
            "id",
            "ticket_code",
            "display_name",
            "phone",
            "service",
            "status",
            "position",
            "joined_at",
            "called_at",
            "waited_minutes",
        ]

    @staticmethod
    def _mask(phone: str) -> str:
        return f"{phone[:6]}...{phone[-3:]}" if len(phone) > 9 else phone

    def get_phone(self, obj) -> str:
        """Masked. A queue board is readable across a reception desk, and a
        full phone number on screen is a needless disclosure."""
        if not obj.patient_id or not obj.patient:
            return ""
        return self._mask(obj.patient.phone)

    def get_display_name(self, obj) -> str:
        """Masked too.

        The model's display_name property falls back to the raw phone when a
        patient has no name on file. Masking `phone` while echoing the same
        number in `display_name` would defeat the point, so the fallback is
        masked here as well.
        """
        if obj.patient_id and obj.patient:
            return obj.patient.full_name or self._mask(obj.patient.phone)
        return obj.walk_in_name or "Walk-in"

    def get_position(self, obj) -> int:
        return obj.position()

    def get_waited_minutes(self, obj) -> int:
        return obj.waited_minutes()


class QueueLocationSerializer(serializers.Serializer):
    lat = serializers.FloatField()
    lng = serializers.FloatField()


class QueueFacilitySerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()
    location = QueueLocationSerializer()


class QueueEntryPublicSerializer(serializers.ModelSerializer):
    """Patient-facing view - no other patient's details, ever.

    Phase 2 adds leave_by and travel_minutes here.
    """

    facility = serializers.SerializerMethodField()
    service = serializers.CharField(source="service_type.code", read_only=True)
    id = serializers.IntegerField(read_only=True)
    ticket_code = serializers.CharField(read_only=True)
    status = serializers.ChoiceField(
        choices=QueueEntry.Status.choices, read_only=True
    )
    joined_at = serializers.DateTimeField(read_only=True)
    position = serializers.SerializerMethodField()
    people_ahead = serializers.SerializerMethodField()
    eta_minutes = serializers.SerializerMethodField()
    eta_confidence = serializers.SerializerMethodField()
    as_of = serializers.SerializerMethodField()

    class Meta:
        model = QueueEntry
        fields = [
            "id",
            "facility",
            "service",
            "ticket_code",
            "status",
            "position",
            "people_ahead",
            "eta_minutes",
            "eta_confidence",
            "joined_at",
            "as_of",
        ]

    def _eta(self, obj):
        from .services import eta_for

        if not hasattr(self, "_eta_cache"):
            self._eta_cache = {}
        if obj.id not in self._eta_cache:
            self._eta_cache[obj.id] = eta_for(obj)
        return self._eta_cache[obj.id]

    @extend_schema_field(QueueFacilitySerializer)
    def get_facility(self, obj) -> dict:
        return {
            "name": obj.facility.name,
            "slug": obj.facility.slug,
            "location": {
                "lat": obj.facility.location.y,
                "lng": obj.facility.location.x,
            },
        }

    def get_position(self, obj) -> int:
        return self._eta(obj)["position"]

    def get_people_ahead(self, obj) -> int:
        return self._eta(obj)["people_ahead"]

    def get_eta_minutes(self, obj) -> int | None:
        return self._eta(obj)["eta_minutes"]

    def get_eta_confidence(self, obj) -> str | None:
        return self._eta(obj)["eta_confidence"]

    def get_as_of(self, obj) -> str:
        from django.utils import timezone

        return timezone.localtime().isoformat()


class SyncActionSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=64)
    type = serializers.ChoiceField(
        choices=["check_in", "call", "serve", "skip", "cancel"]
    )
    client_recorded_at = serializers.DateTimeField()
    payload = serializers.DictField(required=False, default=dict)


class SyncSerializer(serializers.Serializer):
    actions = SyncActionSerializer(many=True)


# --------------------------------------------------------------------------
# Response envelopes - see the note in apps/facilities/serializers.py
# --------------------------------------------------------------------------


class CheckInResponseSerializer(QueueEntrySerializer):
    """The check-in response is an entry plus its live ETA fields."""

    eta_minutes = serializers.IntegerField(allow_null=True)
    eta_confidence = serializers.CharField(allow_null=True)
    people_ahead = serializers.IntegerField()

    class Meta(QueueEntrySerializer.Meta):
        fields = QueueEntrySerializer.Meta.fields + [
            "eta_minutes",
            "eta_confidence",
            "people_ahead",
        ]


class ServiceGroupSerializer(serializers.Serializer):
    service = serializers.CharField()
    service_name_rw = serializers.CharField()
    service_name_en = serializers.CharField()
    waiting = QueueEntrySerializer(many=True)
    called = QueueEntrySerializer(many=True)


class BoardFacilitySerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()


class BoardSerializer(serializers.Serializer):
    facility = BoardFacilitySerializer()
    as_of = serializers.CharField()
    services = ServiceGroupSerializer(many=True)


class SyncResultRowSerializer(serializers.Serializer):
    key = serializers.CharField()
    ok = serializers.BooleanField()
    created = serializers.BooleanField(required=False)
    entry_id = serializers.IntegerField(required=False)
    ticket_code = serializers.CharField(required=False)
    error = serializers.CharField(required=False)


class SyncResponseSerializer(serializers.Serializer):
    applied = serializers.IntegerField()
    rejected = serializers.IntegerField()
    results = SyncResultRowSerializer(many=True)
