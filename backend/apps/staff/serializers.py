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
        """Cross-field checks, resolved against the session as it will END UP.

        The same serializer runs partial for an update, where a request that
        only closes a session sends `{"active": false}` and nothing else. So
        the checks cannot reach into `attrs` unconditionally - that raised
        KeyError on every partial update, a 500 for what should be the safest
        operation on this screen.

        But checking only what the request carried is the opposite mistake,
        and it let two PATCHes through that must not pass. `{"slot_minutes":
        240}` on a half-hour session carries no times to compare against.
        `{"start_time", "end_time"}` that shrinks a session below its stored
        slot length carries no slot length - and comparing against a default
        of zero made the guard a no-op rather than a check. Both produce a
        session that yields zero slots, which reads as broken rather than as
        misconfigured. That is the failure
        `test_a_slot_cannot_be_longer_than_its_session` exists to prevent, and
        it went unprevented on update because the test only ever posted.

        Each field therefore falls back to the stored value when the request
        omits it, and the invariants are checked against the merged result.
        Create passes no instance and requires every field, so the fallbacks
        are unused there.
        """

        def resolved(field):
            if field in attrs:
                return attrs[field]
            return getattr(self.instance, field, None)

        start = resolved("start_time")
        end = resolved("end_time")
        slot = resolved("slot_minutes")

        if start and end:
            if start >= end:
                raise serializers.ValidationError(
                    {"end_time": "The session must end after it starts."}
                )
            span = (
                datetime.combine(date.min, end) - datetime.combine(date.min, start)
            ).total_seconds() / 60
            if slot and span < slot:
                raise serializers.ValidationError(
                    {
                        "slot_minutes": (
                            "A slot cannot be longer than the session that "
                            "holds it."
                        )
                    }
                )
        return attrs


# --------------------------------------------------------------------------
# Insurance - what this facility accepts, maintained by the facility
# --------------------------------------------------------------------------


class StaffServiceCoverageSerializer(serializers.Serializer):
    code = serializers.CharField()
    name_en = serializers.CharField()
    # Matches apps.insurance.models.FacilityServiceInsurer.Coverage.
    coverage = serializers.ChoiceField(
        choices=["full", "partial", "not_covered", "unknown"]
    )
    note = serializers.CharField(allow_blank=True)


class FacilityInsurerSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    accepted = serializers.BooleanField()
    note = serializers.CharField(allow_blank=True)
    confirmed_at = serializers.CharField(allow_null=True)


class InsurerWithCoverageSerializer(FacilityInsurerSerializer):
    services = StaffServiceCoverageSerializer(many=True)


class FacilityInsuranceSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = InsurerWithCoverageSerializer(many=True)


class FacilityInsurerWriteSerializer(serializers.Serializer):
    accepted = serializers.BooleanField()
    # Any condition the facility states, e.g. "referral required". Never a
    # price: we hold no verified cost data and a wrong number would be worse
    # than none.
    note = serializers.CharField(
        required=False, allow_blank=True, max_length=200, default=""
    )


class StaffServiceCoverageWriteSerializer(serializers.Serializer):
    coverage = serializers.ChoiceField(
        choices=["full", "partial", "not_covered", "unknown"]
    )
    note = serializers.CharField(
        required=False, allow_blank=True, max_length=200, default=""
    )


# --------------------------------------------------------------------------
# Facility settings
# --------------------------------------------------------------------------


class OpeningHoursRowSerializer(serializers.Serializer):
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    opens_at = serializers.CharField()
    closes_at = serializers.CharField()


class FacilitySettingsSerializer(serializers.Serializer):
    # Read-only identity. Shown so a manager can see what MediLink verified,
    # and NOT editable here - see the note in views.py.
    name = serializers.CharField()
    level = serializers.CharField()
    ownership = serializers.CharField()
    district = serializers.CharField()
    verified = serializers.BooleanField()

    phone = serializers.CharField(allow_blank=True)
    email = serializers.CharField(allow_blank=True)
    address = serializers.CharField(allow_blank=True)
    sector = serializers.CharField(allow_blank=True)
    hours = OpeningHoursRowSerializer(many=True)


class FacilityContactWriteSerializer(serializers.Serializer):
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    email = serializers.EmailField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True, max_length=255)
    sector = serializers.CharField(required=False, allow_blank=True, max_length=50)


class OpeningHoursWriteRowSerializer(serializers.Serializer):
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    opens_at = serializers.TimeField()
    closes_at = serializers.TimeField()

    def validate(self, attrs):
        if attrs["opens_at"] >= attrs["closes_at"]:
            raise serializers.ValidationError(
                {"closes_at": "A facility must close after it opens."}
            )
        return attrs


class OpeningHoursWriteSerializer(serializers.Serializer):
    """The whole week at once.

    Two rows on one weekday model a lunch break, which is how a Rwandan health
    centre actually runs, so there is no stable "the Tuesday row" to PATCH.
    """

    hours = OpeningHoursWriteRowSerializer(many=True)

    def validate_hours(self, rows):
        # The model enforces (facility, weekday, opens_at) uniqueness. Catching
        # it here gives a sentence rather than a database error.
        seen = set()
        for row in rows:
            key = (row["weekday"], row["opens_at"])
            if key in seen:
                raise serializers.ValidationError(
                    "Two periods on the same day cannot start at the same time."
                )
            seen.add(key)
        return rows


# --------------------------------------------------------------------------
# Patient lookup
# --------------------------------------------------------------------------


class PatientMatchSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    display_name = serializers.CharField(allow_blank=True)
    # Masked. A lookup screen is read across a reception desk.
    phone = serializers.CharField()
    visits_here = serializers.IntegerField()
    last_seen = serializers.CharField(allow_null=True)
    in_queue_now = serializers.BooleanField()
    ticket_code = serializers.CharField(allow_null=True)


class PatientLookupSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    query = serializers.CharField(allow_blank=True)
    results = PatientMatchSerializer(many=True)
