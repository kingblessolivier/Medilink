from django.conf import settings
from rest_framework import serializers

from .models import Facility
from .services import closes_at, is_open_now, opens_next


class NearbyQuerySerializer(serializers.Serializer):
    """Validation is where the Rwanda bounds check belongs.

    Rejecting out-of-bounds coordinates here means a desktop or VPN user gets a
    clear 400 and the district picker, instead of an empty list they cannot
    explain.
    """

    lat = serializers.FloatField(
        min_value=settings.RWANDA_BOUNDS["lat"][0],
        max_value=settings.RWANDA_BOUNDS["lat"][1],
        error_messages={
            "min_value": "lat must be between {min} and {max} (Rwanda).".format(
                min=settings.RWANDA_BOUNDS["lat"][0],
                max=settings.RWANDA_BOUNDS["lat"][1],
            ),
            "max_value": "lat must be between {min} and {max} (Rwanda).".format(
                min=settings.RWANDA_BOUNDS["lat"][0],
                max=settings.RWANDA_BOUNDS["lat"][1],
            ),
        },
    )
    lng = serializers.FloatField(
        min_value=settings.RWANDA_BOUNDS["lng"][0],
        max_value=settings.RWANDA_BOUNDS["lng"][1],
        error_messages={
            "min_value": "lng must be between {min} and {max} (Rwanda).".format(
                min=settings.RWANDA_BOUNDS["lng"][0],
                max=settings.RWANDA_BOUNDS["lng"][1],
            ),
            "max_value": "lng must be between {min} and {max} (Rwanda).".format(
                min=settings.RWANDA_BOUNDS["lng"][0],
                max=settings.RWANDA_BOUNDS["lng"][1],
            ),
        },
    )
    radius = serializers.IntegerField(
        required=False,
        min_value=100,
        max_value=settings.MAX_SEARCH_RADIUS_M,
        default=settings.DEFAULT_SEARCH_RADIUS_M,
    )
    insurer = serializers.SlugField(required=False, allow_null=True)
    service = serializers.SlugField(required=False, allow_null=True)
    level = serializers.ListField(
        child=serializers.SlugField(), required=False, default=list
    )
    open_now = serializers.BooleanField(required=False, default=False)
    limit = serializers.IntegerField(
        required=False, min_value=1, max_value=50, default=20
    )


class LocationField(serializers.Serializer):
    lat = serializers.FloatField()
    lng = serializers.FloatField()


class WaitSerializer(serializers.Serializer):
    status = serializers.CharField()
    minutes = serializers.IntegerField(allow_null=True)
    people_waiting = serializers.IntegerField(allow_null=True)
    as_of = serializers.CharField()


class FacilityNearbySerializer(serializers.ModelSerializer):
    distance_m = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    is_open = serializers.BooleanField(read_only=True)
    accepts_insurer = serializers.BooleanField(read_only=True)
    insurers = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()
    opens_at = serializers.SerializerMethodField()
    closes_at = serializers.SerializerMethodField()
    closing_soon = serializers.SerializerMethodField()
    wait = serializers.SerializerMethodField()
    bookable = serializers.SerializerMethodField()

    class Meta:
        model = Facility
        fields = [
            "id",
            "slug",
            "name",
            "level",
            "ownership",
            "district",
            "sector",
            "location",
            "distance_m",
            "phone",
            "is_open",
            "opens_at",
            "closes_at",
            "closing_soon",
            "accepts_insurer",
            "insurers",
            "services",
            "wait",
            "bookable",
        ]

    def get_distance_m(self, obj) -> int:
        return round(obj.distance.m)

    def get_location(self, obj) -> dict:
        return {"lat": obj.location.y, "lng": obj.location.x}

    def get_insurers(self, obj) -> list:
        return [fi.insurer.code for fi in obj.insurers.all()]

    def get_services(self, obj) -> list:
        return [fs.service_type.code for fs in obj.services.all() if fs.available]

    def get_opens_at(self, obj):
        value = opens_next(obj)
        return value.strftime("%H:%M") if value else None

    def get_closes_at(self, obj):
        value = closes_at(obj)
        return value.strftime("%H:%M") if value else None

    def get_closing_soon(self, obj) -> bool:
        """A patient must not travel to a door that shuts on arrival."""
        from datetime import datetime, timedelta

        from django.utils import timezone

        value = closes_at(obj)
        if value is None:
            return False
        now = timezone.localtime()
        closing = datetime.combine(now.date(), value)
        return closing - now.replace(tzinfo=None) < timedelta(minutes=30)

    def get_wait(self, obj) -> dict:
        return self.context["waits"][obj.id]

    def get_bookable(self, obj) -> bool:
        # Booking arrives in Phase 2. Until a facility runs the reception tool
        # there is nothing to book against.
        return False


class OpeningHoursSerializer(serializers.Serializer):
    weekday = serializers.IntegerField()
    opens_at = serializers.TimeField(format="%H:%M")
    closes_at = serializers.TimeField(format="%H:%M")


class FacilityDetailSerializer(serializers.ModelSerializer):
    location = serializers.SerializerMethodField()
    is_open = serializers.SerializerMethodField()
    opening_hours = OpeningHoursSerializer(many=True, read_only=True)
    insurers = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()
    wait = serializers.SerializerMethodField()
    directions_url = serializers.SerializerMethodField()

    class Meta:
        model = Facility
        fields = [
            "id",
            "slug",
            "name",
            "level",
            "ownership",
            "province",
            "district",
            "sector",
            "address",
            "location",
            "phone",
            "email",
            "is_open",
            "opening_hours",
            "insurers",
            "services",
            "wait",
            "directions_url",
            "verified_at",
        ]

    def get_location(self, obj) -> dict:
        return {"lat": obj.location.y, "lng": obj.location.x}

    def get_is_open(self, obj) -> bool:
        return is_open_now(obj)

    def get_insurers(self, obj) -> list:
        return [
            {"code": fi.insurer.code, "name": fi.insurer.name, "note": fi.note}
            for fi in obj.insurers.all()
        ]

    def get_services(self, obj) -> list:
        return [
            {
                "code": fs.service_type.code,
                "name_rw": fs.service_type.name_rw,
                "name_en": fs.service_type.name_en,
                "name_fr": fs.service_type.name_fr,
            }
            for fs in obj.services.all()
            if fs.available
        ]

    def get_wait(self, obj) -> dict:
        return self.context["waits"][obj.id]

    def get_directions_url(self, obj) -> str:
        # We do not build routing. Every Android phone already has a maps app
        # that does this better than we would.
        return (
            "https://www.google.com/maps/dir/?api=1&destination="
            f"{obj.location.y},{obj.location.x}"
        )
