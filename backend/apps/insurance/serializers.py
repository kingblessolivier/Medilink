from rest_framework import serializers


class InsurerSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    is_public = serializers.BooleanField()


class InsurerListSerializer(serializers.Serializer):
    results = InsurerSerializer(many=True)
