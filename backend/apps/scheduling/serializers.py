from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Appointment


class SlotQuerySerializer(serializers.Serializer):
    service = serializers.SlugField()
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)


class SlotSerializer(serializers.Serializer):
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    # Slots with remaining == 0 are returned rather than omitted, so the UI can
    # grey them out: a patient needs to see that a day is busy, not empty.
    remaining = serializers.IntegerField()
    capacity = serializers.IntegerField()


class SlotDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    slots = SlotSerializer(many=True)


class SlotDaysSerializer(serializers.Serializer):
    facility = serializers.CharField()
    service = serializers.CharField()
    as_of = serializers.CharField()
    days = SlotDaySerializer(many=True)


class BookingSerializer(serializers.Serializer):
    facility = serializers.SlugField()
    service = serializers.SlugField()
    slot_start = serializers.DateTimeField()


class AppointmentFacilitySerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()
    phone = serializers.CharField(allow_blank=True)


class AppointmentSerializer(serializers.ModelSerializer):
    facility = serializers.SerializerMethodField()
    service = serializers.CharField(source="service_type.code", read_only=True)
    id = serializers.IntegerField(read_only=True)
    reference = serializers.CharField(read_only=True)
    status = serializers.ChoiceField(
        choices=Appointment.Status.choices, read_only=True
    )
    slot_start = serializers.DateTimeField(read_only=True)
    slot_end = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "reference",
            "status",
            "facility",
            "service",
            "slot_start",
            "slot_end",
        ]

    @extend_schema_field(AppointmentFacilitySerializer)
    def get_facility(self, obj) -> dict:
        return {
            "name": obj.facility.name,
            "slug": obj.facility.slug,
            "phone": obj.facility.phone,
        }
