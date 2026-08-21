from django.conf import settings
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Facility
from .services import closes_at, is_open_now, opens_next
from .wait import ALL_STATUSES


class NearbyQuerySerializer(serializers.Serializer):
    """Validation is where the Rwanda bounds check belongs.

    Rejecting out-of-bounds coordinates here means a desktop or VPN user gets a
    clear 400 and the district picker, instead of an empty list they cannot
    explain.
    """

    lat = serializers.FloatField(
        required=False,
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
        required=False,
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
    # Set by the Care Guide. Ignored when `service` is given - an explicit
    # service choice by the patient always wins over an inference.
    specialty = serializers.SlugField(required=False, allow_null=True)
    level = serializers.ListField(
        child=serializers.SlugField(), required=False, default=list
    )
    open_now = serializers.BooleanField(required=False, default=False)
    limit = serializers.IntegerField(
        required=False, min_value=1, max_value=50, default=20
    )
    # The fallback when a browser will not give up a location - denied, an
    # insecure origin, or a device that simply has no fix. The patient says
    # which district they are in and gets that district's facilities.
    district = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        """One of a coordinate pair or a district, and lat/lng come together.

        Enforced here rather than in the view so the error names the field a
        client can act on, and so the schema marks all three as optional
        without implying any combination will do.
        """
        has_point = attrs.get("lat") is not None and attrs.get("lng") is not None
        half_a_point = ("lat" in attrs) != ("lng" in attrs)

        if half_a_point:
            raise serializers.ValidationError(
                {"lng": "lat and lng must be given together."}
            )
        if not has_point and not attrs.get("district"):
            raise serializers.ValidationError(
                {"district": "Give lat and lng, or a district."}
            )
        return attrs


class LocationField(serializers.Serializer):
    lat = serializers.FloatField()
    lng = serializers.FloatField()


class InsurerBriefSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    note = serializers.CharField(allow_blank=True)


class ServiceCoverageSerializer(serializers.Serializer):
    insurer = serializers.CharField()
    insurer_name = serializers.CharField()
    # full | partial | not_covered | unknown. Defaults to unknown, and an
    # unconfirmed row reads as unknown however it was entered.
    coverage = serializers.CharField()
    note = serializers.CharField(allow_blank=True)


class WaitSerializer(serializers.Serializer):
    """The wait contract, enforced in the OpenAPI schema itself.

    `status` is a ChoiceField rather than a CharField so the generated
    TypeScript client gets a closed union and a client that forgets to
    handle one of the four states fails to compile. There is deliberately
    no value meaning "estimated" - we never guess a wait time.

    Defined above ServiceBriefSerializer because that one embeds it.
    """

    status = serializers.ChoiceField(choices=ALL_STATUSES)
    minutes = serializers.IntegerField(allow_null=True)
    people_waiting = serializers.IntegerField(allow_null=True)
    as_of = serializers.CharField()


class ServiceBriefSerializer(serializers.Serializer):
    code = serializers.CharField()
    name_rw = serializers.CharField()
    name_en = serializers.CharField()
    name_fr = serializers.CharField()
    # Per-service live status: "General consultation - 32 min" rather than one
    # number for the whole hospital.
    wait = WaitSerializer()
    coverage = ServiceCoverageSerializer(many=True)


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

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_distance_m(self, obj) -> int | None:
        """Null when the search had no origin.

        A district search knows the patient is in Gasabo and nothing more, so
        there is no honest distance to report. Null rather than 0 or a
        district-centroid guess: the client hides the line, which is correct,
        whereas a fabricated number would be acted on.
        """
        distance = getattr(obj, "distance", None)
        return round(distance.m) if distance is not None else None

    @extend_schema_field(LocationField)
    def get_location(self, obj) -> dict:
        return {"lat": obj.location.y, "lng": obj.location.x}

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_insurers(self, obj) -> list:
        return [fi.insurer.code for fi in obj.insurers.all()]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_services(self, obj) -> list:
        return [fs.service_type.code for fs in obj.services.all() if fs.available]

    def get_opens_at(self, obj) -> str | None:
        value = opens_next(obj)
        return value.strftime("%H:%M") if value else None

    def get_closes_at(self, obj) -> str | None:
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

    @extend_schema_field(WaitSerializer)
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

    @extend_schema_field(LocationField)
    def get_location(self, obj) -> dict:
        return {"lat": obj.location.y, "lng": obj.location.x}

    def get_is_open(self, obj) -> bool:
        return is_open_now(obj)

    @extend_schema_field(InsurerBriefSerializer(many=True))
    def get_insurers(self, obj) -> list:
        return [
            {"code": fi.insurer.code, "name": fi.insurer.name, "note": fi.note}
            for fi in obj.insurers.all()
        ]

    @extend_schema_field(ServiceBriefSerializer(many=True))
    def get_services(self, obj) -> list:
        waits = self.context.get("service_waits", {})
        unknown = {
            "status": "not_reported",
            "minutes": None,
            "people_waiting": None,
            "as_of": "",
        }
        return [
            {
                "code": fs.service_type.code,
                "name_rw": fs.service_type.name_rw,
                "name_en": fs.service_type.name_en,
                "name_fr": fs.service_type.name_fr,
                "wait": waits.get(fs.service_type.code, unknown),
                "coverage": [
                    {
                        "insurer": c.insurer.code,
                        "insurer_name": c.insurer.name,
                        # effective_coverage, not coverage: somebody part-way
                        # through entering data must not publish a claim.
                        "coverage": c.effective_coverage,
                        "note": c.note,
                    }
                    for c in fs.insurer_coverage.all()
                ],
            }
            for fs in obj.services.all()
            if fs.available
        ]

    @extend_schema_field(WaitSerializer)
    def get_wait(self, obj) -> dict:
        return self.context["waits"][obj.id]

    def get_directions_url(self, obj) -> str:
        # We do not build routing. Every Android phone already has a maps app
        # that does this better than we would.
        return (
            "https://www.google.com/maps/dir/?api=1&destination="
            f"{obj.location.y},{obj.location.x}"
        )


# --------------------------------------------------------------------------
# Response envelopes
#
# These exist so drf-spectacular can describe response bodies. Without them the
# generated OpenAPI schema has no response shapes, the generated TypeScript
# client is empty, and the CI contract check becomes a no-op. See docs/01 s9.
# --------------------------------------------------------------------------


class NearbyQueryEchoSerializer(serializers.Serializer):
    # Null on a district search - there was no coordinate to echo back.
    lat = serializers.FloatField(allow_null=True)
    lng = serializers.FloatField(allow_null=True)
    district = serializers.CharField(allow_null=True)
    radius = serializers.IntegerField()
    radius_expanded = serializers.BooleanField()
    insurer = serializers.CharField(allow_null=True)
    service = serializers.CharField(allow_null=True)
    specialty = serializers.CharField(allow_null=True)
    open_now = serializers.BooleanField()


class NearbyResponseSerializer(serializers.Serializer):
    as_of = serializers.CharField()
    query = NearbyQueryEchoSerializer()
    count = serializers.IntegerField()
    results = FacilityNearbySerializer(many=True)


class ServiceTypeSerializer(serializers.Serializer):
    code = serializers.CharField()
    name_rw = serializers.CharField()
    name_en = serializers.CharField()
    name_fr = serializers.CharField()


class ServiceTypeListSerializer(serializers.Serializer):
    results = ServiceTypeSerializer(many=True)


class DistrictListSerializer(serializers.Serializer):
    results = serializers.ListField(child=serializers.CharField())
