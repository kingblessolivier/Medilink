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


# --------------------------------------------------------------------------
# Oversight: what is happening on the platform
# --------------------------------------------------------------------------


class AdminFacilitySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    district = serializers.CharField()
    level = serializers.CharField()
    ownership = serializers.CharField()
    verified = serializers.BooleanField()
    reports_queue = serializers.BooleanField()
    # A verified facility with no active staff account cannot check anybody
    # in. It looks fine from the patient side and is silently doing nothing.
    staff_count = serializers.IntegerField()
    service_count = serializers.IntegerField()


class AdminFacilityListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = AdminFacilitySerializer(many=True)


class AdminProviderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    full_name = serializers.CharField()
    verified = serializers.BooleanField()
    specialties = serializers.ListField(child=serializers.CharField())
    facilities = serializers.ListField(child=serializers.CharField())


class AdminProviderListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = AdminProviderSerializer(many=True)


class AdminStaffSerializer(serializers.Serializer):
    """An access-control list, not a personnel list."""

    id = serializers.IntegerField()
    username = serializers.CharField()
    facility = serializers.CharField()
    role = serializers.CharField()
    active = serializers.BooleanField()
    can_manage_queue = serializers.BooleanField()
    last_login = serializers.DateTimeField(allow_null=True)


class AdminStaffListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = AdminStaffSerializer(many=True)
    accounts = serializers.DictField(child=serializers.IntegerField())


class ActivityTotalsSerializer(serializers.Serializer):
    waiting_now = serializers.IntegerField()
    seen = serializers.IntegerField()
    booked = serializers.IntegerField()
    no_shows = serializers.IntegerField()
    facilities_active = serializers.IntegerField()


class ActivityFacilitySerializer(serializers.Serializer):
    name = serializers.CharField()
    district = serializers.CharField()
    waiting = serializers.IntegerField()
    seen = serializers.IntegerField()
    booked = serializers.IntegerField()
    reports_queue = serializers.BooleanField()


class PlatformActivitySerializer(serializers.Serializer):
    days = serializers.IntegerField()
    as_of = serializers.DateTimeField()
    totals = ActivityTotalsSerializer()
    facilities = ActivityFacilitySerializer(many=True)


class AccessActorSerializer(serializers.Serializer):
    actor = serializers.CharField()
    facility = serializers.CharField()
    events = serializers.IntegerField()


class AccessEventSerializer(serializers.Serializer):
    """The patient is deliberately absent. Who did the touching, how much and
    when is what an access review needs; naming the patient would make the
    oversight tool its own disclosure risk."""

    id = serializers.IntegerField()
    occurred_at = serializers.DateTimeField()
    actor = serializers.CharField()
    action = serializers.CharField()
    action_label = serializers.CharField()
    facility = serializers.CharField()
    record_count = serializers.IntegerField()
    ip_address = serializers.CharField(allow_null=True)


class AccessLogSerializer(serializers.Serializer):
    days = serializers.IntegerField()
    as_of = serializers.DateTimeField()
    total_events = serializers.IntegerField()
    by_actor = AccessActorSerializer(many=True)
    recent = AccessEventSerializer(many=True)


class DeliveryKindSerializer(serializers.Serializer):
    kind = serializers.CharField()
    total = serializers.IntegerField()
    sent = serializers.IntegerField()
    failed = serializers.IntegerField()


class DeliveryReportSerializer(serializers.Serializer):
    days = serializers.IntegerField()
    total = serializers.IntegerField()
    sent = serializers.IntegerField()
    failed = serializers.IntegerField()
    # Null when nothing was sent: no messages is not a 100% success rate.
    failure_rate = serializers.FloatField(allow_null=True)
    by_kind = DeliveryKindSerializer(many=True)
