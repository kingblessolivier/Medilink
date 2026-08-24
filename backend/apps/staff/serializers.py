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
