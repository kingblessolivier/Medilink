from django.contrib.gis.geos import Point
from rest_framework import serializers

from apps.insurance.models import Insurer

from .models import Patient


class OTPRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)


class OTPVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(min_length=6, max_length=6)


class HomeLocationSerializer(serializers.Serializer):
    lat = serializers.FloatField()
    lng = serializers.FloatField()


class PatientSerializer(serializers.ModelSerializer):
    insurer = serializers.SlugRelatedField(
        slug_field="code",
        queryset=Insurer.objects.all(),
        allow_null=True,
        required=False,
    )
    home_location = serializers.SerializerMethodField()
    id = serializers.IntegerField(read_only=True)
    phone = serializers.CharField(read_only=True)

    class Meta:
        model = Patient
        fields = ["id", "phone", "full_name", "language", "insurer", "home_location"]

    def get_home_location(self, obj) -> dict | None:
        if obj.home_location is None:
            return None
        return {"lat": obj.home_location.y, "lng": obj.home_location.x}

    def to_internal_value(self, data):
        validated = super().to_internal_value(data)
        # home_location is opt-in and only improves the "leave home by"
        # estimate. Accepted as {lat, lng}; stored as a Point, longitude first.
        if "home_location" in data:
            location = data.get("home_location")
            if location is None:
                validated["home_location"] = None
            else:
                coords = HomeLocationSerializer(data=location)
                coords.is_valid(raise_exception=True)
                validated["home_location"] = Point(
                    coords.validated_data["lng"],
                    coords.validated_data["lat"],
                    srid=4326,
                )
        return validated


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    patient = PatientSerializer()
