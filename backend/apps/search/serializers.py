from django.conf import settings
from rest_framework import serializers


class SearchQuerySerializer(serializers.Serializer):
    q = serializers.CharField(max_length=80, allow_blank=True)
    # Optional: with a location, facility results are ordered nearest first.
    lat = serializers.FloatField(
        required=False,
        min_value=settings.RWANDA_BOUNDS["lat"][0],
        max_value=settings.RWANDA_BOUNDS["lat"][1],
    )
    lng = serializers.FloatField(
        required=False,
        min_value=settings.RWANDA_BOUNDS["lng"][0],
        max_value=settings.RWANDA_BOUNDS["lng"][1],
    )


class SearchResultSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()
    label_rw = serializers.CharField(required=False)
    label_fr = serializers.CharField(required=False)
    sublabel = serializers.CharField(required=False)
    distance_m = serializers.IntegerField(required=False, allow_null=True)
    href = serializers.CharField()
    # False for a specialty that maps to no facility service - the client
    # shows it, but cannot navigate anywhere useful from it.
    routable = serializers.BooleanField()


class SearchGroupSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(
        choices=["specialty", "service", "provider", "facility"]
    )
    results = SearchResultSerializer(many=True)


class SearchResponseSerializer(serializers.Serializer):
    query = serializers.CharField()
    groups = SearchGroupSerializer(many=True)
