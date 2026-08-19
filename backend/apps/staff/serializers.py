from rest_framework import serializers


class StaffFacilitySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    name = serializers.CharField()
    district = serializers.CharField()
    reports_queue = serializers.BooleanField()


class StaffServiceSerializer(serializers.Serializer):
    code = serializers.CharField()
    name_rw = serializers.CharField()
    name_en = serializers.CharField()


class StaffMeSerializer(serializers.Serializer):
    username = serializers.CharField()
    role = serializers.CharField()
    can_manage_queue = serializers.BooleanField()
    facility = StaffFacilitySerializer()
    services = StaffServiceSerializer(many=True)
