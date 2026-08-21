from rest_framework import serializers


# --------------------------------------------------------------------------
# Overview
# --------------------------------------------------------------------------


class FacilityCountsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    verified = serializers.IntegerField()
    awaiting_verification = serializers.IntegerField()
    reporting_queue = serializers.IntegerField()


class ProviderCountsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    verified = serializers.IntegerField()
    awaiting_verification = serializers.IntegerField()


class PatientCountsSerializer(serializers.Serializer):
    # A count. There is deliberately no endpoint returning a patient list.
    registered = serializers.IntegerField()


class ChannelCountSerializer(serializers.Serializer):
    channel = serializers.CharField()
    count = serializers.IntegerField()


class ActivitySerializer(serializers.Serializer):
    check_ins = serializers.IntegerField()
    appointments = serializers.IntegerField()
    by_channel = ChannelCountSerializer(many=True)


class AdminOverviewSerializer(serializers.Serializer):
    days = serializers.IntegerField()
    as_of = serializers.DateTimeField()
    facilities = FacilityCountsSerializer()
    providers = ProviderCountsSerializer()
    patients = PatientCountsSerializer()
    activity = ActivitySerializer()


# --------------------------------------------------------------------------
# Verification queue
# --------------------------------------------------------------------------


class PendingFacilitySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    district = serializers.CharField()
    level = serializers.CharField()
    ownership = serializers.CharField()
    phone = serializers.CharField(allow_blank=True)


class PendingProviderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    full_name = serializers.CharField()
    specialties = serializers.ListField(child=serializers.CharField())


class VerificationQueueSerializer(serializers.Serializer):
    facilities = PendingFacilitySerializer(many=True)
    providers = PendingProviderSerializer(many=True)


class VerifySerializer(serializers.Serializer):
    """Verifying is an assertion that somebody checked documents.

    The note is required for exactly that reason: an approval with no record
    of what was checked is indistinguishable from a mis-click, and this one
    puts a facility in front of patients.
    """

    note = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)


class VerifiedSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    verified_at = serializers.DateTimeField()
    verified_by = serializers.CharField(allow_null=True)


# --------------------------------------------------------------------------
# Triage monitoring
# --------------------------------------------------------------------------


class TriageServiceCountSerializer(serializers.Serializer):
    service = serializers.CharField()
    count = serializers.IntegerField()


class TriageVersionSerializer(serializers.Serializer):
    protocol_version = serializers.CharField()
    sessions = serializers.IntegerField()
    escalations = serializers.IntegerField()


class TriageMonitoringSerializer(serializers.Serializer):
    days = serializers.IntegerField()
    sessions = serializers.IntegerField()
    escalations = serializers.IntegerField()
    # Null under the floor, so nobody tunes a protocol on four sessions.
    escalation_rate = serializers.FloatField(allow_null=True)
    enough_data = serializers.BooleanField()
    minimum_sessions = serializers.IntegerField()
    by_service = TriageServiceCountSerializer(many=True)
    by_version = TriageVersionSerializer(many=True)
