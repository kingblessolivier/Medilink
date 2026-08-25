from datetime import date, datetime

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


# --------------------------------------------------------------------------
# Workspace: appointments
# --------------------------------------------------------------------------


class StaffAppointmentSerializer(serializers.Serializer):
    """One row on the facility's appointment list.

    Staff at the facility a patient booked with see the patient's name and
    phone: they have to call somebody who has not arrived, and reception has
    always had this. It is scoped to their own facility and written to the
    audit log - see apps/patients/models.PatientAccessLog.
    """

    id = serializers.IntegerField()
    reference = serializers.CharField()
    slot_start = serializers.DateTimeField()
    slot_end = serializers.DateTimeField()
    status = serializers.CharField()
    booked_via = serializers.CharField()
    service = serializers.CharField()
    service_code = serializers.CharField()
    provider = serializers.CharField(allow_null=True)
    patient_name = serializers.CharField()
    patient_phone = serializers.CharField(allow_null=True)


class StaffAppointmentListSerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField()
    results = StaffAppointmentSerializer(many=True)


# --------------------------------------------------------------------------
# Workspace: reports
# --------------------------------------------------------------------------


class ReportTodaySerializer(serializers.Serializer):
    checked_in = serializers.IntegerField()
    waiting = serializers.IntegerField()
    served = serializers.IntegerField()


class ReportPeriodSerializer(serializers.Serializer):
    checked_in = serializers.IntegerField()
    served = serializers.IntegerField()
    left_without_being_seen = serializers.IntegerField()


class ReportWaitSerializer(serializers.Serializer):
    # Null, never zero, when the sample is too small to be honest about.
    median_minutes = serializers.FloatField(allow_null=True)
    sample_size = serializers.IntegerField()
    this_week_minutes = serializers.FloatField(allow_null=True)
    last_week_minutes = serializers.FloatField(allow_null=True)
    enough_data = serializers.BooleanField()


class ReportAppointmentsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    no_shows = serializers.IntegerField()
    no_show_rate = serializers.FloatField(allow_null=True)
    unrecorded = serializers.IntegerField()


class ReportDemandSerializer(serializers.Serializer):
    service = serializers.CharField()
    count = serializers.IntegerField()


class FacilityReportSerializer(serializers.Serializer):
    facility = serializers.CharField()
    days = serializers.IntegerField()
    as_of = serializers.DateTimeField()
    today = ReportTodaySerializer()
    period = ReportPeriodSerializer()
    wait = ReportWaitSerializer()
    appointments = ReportAppointmentsSerializer()
    demand = ReportDemandSerializer(many=True)


class AppointmentStatusSerializer(serializers.Serializer):
    """The three transitions reception performs from the appointment list.

    Cancellation is absent on purpose: a facility cancelling on a patient owes
    them a message, so it goes through the scheduling endpoint that sends one.
    """

    status = serializers.ChoiceField(choices=["arrived", "served", "no_show"])


# --------------------------------------------------------------------------
# Schedule templates - the facility's own bookable hours
# --------------------------------------------------------------------------


class ScheduleTemplateSerializer(serializers.Serializer):
    """One recurring weekly session.

    Read shape. `upcoming` is the count of appointments already booked against
    this session in the future - the number a facility needs before it decides
    to close a session, because deactivating stops new bookings and does NOT
    cancel the patients who already hold one.
    """

    id = serializers.IntegerField(read_only=True)
    weekday = serializers.IntegerField()
    service = serializers.CharField()
    service_name_en = serializers.CharField()
    service_name_rw = serializers.CharField()
    provider = serializers.CharField(allow_null=True)
    provider_name = serializers.CharField(allow_null=True)
    start_time = serializers.CharField()
    end_time = serializers.CharField()
    slot_minutes = serializers.IntegerField()
    capacity_per_slot = serializers.IntegerField()
    active = serializers.BooleanField()
    slots_per_week = serializers.IntegerField()
    upcoming = serializers.IntegerField()


class ScheduleTemplateListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = ScheduleTemplateSerializer(many=True)


class ScheduleTemplateWriteSerializer(serializers.Serializer):
    """Create or update a session.

    `provider` is a slug or omitted. Omitted means the facility's general
    clinic - the session where staff assign whoever is free, which is how most
    booking at a health centre actually works.
    """

    weekday = serializers.IntegerField(min_value=0, max_value=6)
    service = serializers.SlugField()
    provider = serializers.SlugField(required=False, allow_null=True, allow_blank=True)
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    # 5 minutes is the shortest sane consultation slot; 4 hours the longest.
    slot_minutes = serializers.IntegerField(min_value=5, max_value=240)
    capacity_per_slot = serializers.IntegerField(min_value=1, max_value=50)
    active = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        """Cross-field checks, written to survive a PATCH.

        The same serializer runs partial for an update, where a request that
        only closes a session sends `{"active": false}` and nothing else. The
        checks below therefore run only when the fields they compare are
        actually present - reaching into `attrs` unconditionally raised
        KeyError on every partial update, which is a 500 for what should be
        the safest operation on this screen.
        """
        start = attrs.get("start_time")
        end = attrs.get("end_time")
        if start and end:
            if start >= end:
                raise serializers.ValidationError(
                    {"end_time": "The session must end after it starts."}
                )
            span = (
                datetime.combine(date.min, end) - datetime.combine(date.min, start)
            ).total_seconds() / 60
            if span < attrs.get("slot_minutes", 0):
                raise serializers.ValidationError(
                    {
                        "slot_minutes": (
                            "A slot cannot be longer than the session that "
                            "holds it."
                        )
                    }
                )
        return attrs
