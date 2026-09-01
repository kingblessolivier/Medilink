from rest_framework import serializers


class InsurerSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    is_public = serializers.BooleanField()


class InsurerListSerializer(serializers.Serializer):
    """Envelope for the reference list.

    Declared so drf-spectacular can type the response of a function-based
    view; the view itself builds the payload directly.
    """

    results = InsurerSerializer(many=True)
