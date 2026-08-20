from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Provider, Specialty


class SpecialtySerializer(serializers.ModelSerializer):
    service_types = serializers.SerializerMethodField()

    class Meta:
        model = Specialty
        fields = [
            "code",
            "name_rw",
            "name_en",
            "name_fr",
            "description_en",
            "service_types",
            "is_triage_target",
        ]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_service_types(self, obj) -> list:
        return [s.code for s in obj.service_types.all()]


class SpecialtyListSerializer(serializers.Serializer):
    results = SpecialtySerializer(many=True)


class PlacementSerializer(serializers.Serializer):
    facility_slug = serializers.CharField()
    facility_name = serializers.CharField()
    district = serializers.CharField()
    role_title = serializers.CharField(allow_blank=True)
    services = serializers.ListField(child=serializers.CharField())


class ProviderSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    initials = serializers.CharField(read_only=True)

    # Declared read-only so the schema marks them as always present in a
    # response. Model fields with defaults are otherwise emitted as optional,
    # which forces every client into needless undefined checks.
    slug = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    photo_url = serializers.CharField(read_only=True, allow_blank=True)
    languages = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )
    specialties = serializers.SerializerMethodField()
    placements = serializers.SerializerMethodField()
    verified = serializers.SerializerMethodField()

    class Meta:
        model = Provider
        fields = [
            "slug",
            "display_name",
            "full_name",
            "initials",
            "photo_url",
            "languages",
            "specialties",
            "placements",
            "verified",
        ]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_specialties(self, obj) -> list:
        return [s.code for s in obj.specialties.all()]

    def get_verified(self, obj) -> bool:
        return obj.is_verified

    @extend_schema_field(PlacementSerializer(many=True))
    def get_placements(self, obj) -> list:
        # `visible_placements` is attached by providers_queryset() and is
        # already filtered to active placements at verified facilities.
        placements = getattr(obj, "visible_placements", None)
        if placements is None:
            placements = obj.placements.filter(active=True).select_related("facility")
        return [
            {
                "facility_slug": p.facility.slug,
                "facility_name": p.facility.name,
                "district": p.facility.district,
                "role_title": p.role_title,
                "services": [s.code for s in p.service_types.all()],
            }
            for p in placements
        ]


class ProviderDetailSerializer(ProviderSerializer):
    class Meta(ProviderSerializer.Meta):
        fields = ProviderSerializer.Meta.fields + ["bio_en"]


class ProviderListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = ProviderSerializer(many=True)


class ProviderQuerySerializer(serializers.Serializer):
    specialty = serializers.SlugField(required=False)
    facility = serializers.SlugField(required=False)
    service = serializers.SlugField(required=False)
    language = serializers.ChoiceField(
        choices=["rw", "en", "fr", "sw"], required=False
    )
    search = serializers.CharField(required=False, max_length=80)
    limit = serializers.IntegerField(required=False, default=20, min_value=1, max_value=50)
