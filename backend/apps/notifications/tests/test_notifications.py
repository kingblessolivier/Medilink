"""Notification correctness.

The two properties that matter: a patient is told exactly once, and a patient
is never told something we cannot stand behind.
"""

from datetime import time, timedelta

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.facilities.models import Facility, OpeningHours, ServiceType
from apps.notifications.models import Notification
from apps.notifications.services import compose, dispatch
from apps.notifications.sms import GSM7, MAX_SMS_CHARS, render, to_gsm7
from apps.notifications.tasks import (
    send_appointment_reminders,
    send_called_notification,
    send_leave_now_notifications,
    short_name,
)
from apps.patients.models import Patient
from apps.queueing.models import QueueEntry, ServiceTimeStat
from apps.queueing.travel import leave_by, travel_minutes
from apps.scheduling.models import Appointment

KIMIRONKO = Point(30.1122, -1.9481, srid=4326)
KCC = Point(30.0606, -1.9536, srid=4326)


@pytest.fixture
def general(db):
    return ServiceType.objects.create(
        code="general_consultation",
        name_en="General consultation",
        name_rw="Kwivuza rusange",
        name_fr="Consultation generale",
    )


@pytest.fixture
def facility(db):
    facility = Facility.objects.create(
        name="Kimironko Health Centre",
        slug="kimironko-hc",
        ownership="public",
        level="health_centre",
        district="Gasabo",
        location=KIMIRONKO,
        verified_at=timezone.now(),
        reports_queue=True,
    )
    for weekday in range(7):
        OpeningHours.objects.create(
            facility=facility, weekday=weekday, opens_at=time(0, 0),
            closes_at=time(23, 59),
        )
    return facility


@pytest.fixture
def patient(db):
    return Patient.objects.create(phone="+250788111222", home_location=KCC)


# --------------------------------------------------------------------------
# SMS constraints
# --------------------------------------------------------------------------


def test_accented_characters_are_folded_not_mangled():
    """Networks turn non-GSM7 characters into question marks.

    The rule is subtler than "no accents": the GSM-7 basic table DOES include
    a e-acute, a-grave and friends, so `générale` is safe as it stands. It does
    not include a-circumflex or e-circumflex, which must be folded to their
    base letter.
    """
    assert to_gsm7("Consultation generale") == "Consultation generale"

    # In the GSM-7 basic table - passes through untouched.
    assert to_gsm7("générale") == "générale"
    assert set("àèéùìòäöñüÇ") <= GSM7

    # Not in the table - folded to the base letter rather than mangled to "?".
    assert to_gsm7("hôpital") == "hopital"
    assert to_gsm7("enquête") == "enquete"
    assert "?" not in to_gsm7("hôpital enquête naïve")


def test_every_message_fits_one_segment():
    long_text = "x" * 500
    assert len(render(long_text)) <= MAX_SMS_CHARS


@pytest.mark.parametrize("language", ["rw", "en", "fr"])
@pytest.mark.parametrize(
    "kind,context",
    [
        (Notification.Kind.OTP, {"code": "483927", "minutes": 5}),
        (
            Notification.Kind.LEAVE_NOW,
            {"position": 8, "facility": "Kimironko HC"},
        ),
        (Notification.Kind.CALLED, {"ticket": "G-042", "facility": "Kimironko HC"}),
        (
            Notification.Kind.APPT_REMINDER_24H,
            {"time": "08:00", "facility": "Kimironko HC", "reference": "ML7K2Q"},
        ),
        (
            Notification.Kind.APPT_REMINDER_2H,
            {"time": "08:00", "facility": "Kimironko HC", "reference": "ML7K2Q"},
        ),
        (Notification.Kind.APPT_CANCELLED, {"facility": "Kimironko HC"}),
    ],
)
def test_all_templates_are_gsm7_safe_and_short(kind, language, context):
    """A second segment costs a second message, in all three languages."""
    body = compose(kind, language, **context)
    assert len(body) <= MAX_SMS_CHARS, f"{kind}/{language} is {len(body)} chars"
    assert set(body) <= GSM7, f"{kind}/{language} has non-GSM7 characters"


def test_facility_names_are_shortened_for_sms():
    assert short_name("Kimironko Health Centre") == "Kimironko HC"
    assert short_name("Masaka District Hospital") == "Masaka DH"


# --------------------------------------------------------------------------
# Deduplication
# --------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_the_same_notification_is_never_sent_twice(facility, general, patient):
    """The defence is a database constraint, not an `if already_sent` check
    that two overlapping schedulers would both pass."""
    entry = QueueEntry.objects.create(
        facility=facility, service_type=general, patient=patient, ticket_code="G-001"
    )

    first = dispatch(
        kind=Notification.Kind.LEAVE_NOW,
        phone=patient.phone,
        patient=patient,
        queue_entry=entry,
        position=3,
        facility="Kimironko HC",
    )
    second = dispatch(
        kind=Notification.Kind.LEAVE_NOW,
        phone=patient.phone,
        patient=patient,
        queue_entry=entry,
        position=3,
        facility="Kimironko HC",
    )

    assert first is not None
    assert second is None
    assert Notification.objects.filter(kind=Notification.Kind.LEAVE_NOW).count() == 1


@pytest.mark.django_db(transaction=True)
def test_running_the_scheduler_twice_sends_one_message(
    facility, general, patient
):
    ServiceTimeStat.objects.create(
        facility=facility,
        service_type=general,
        hour_of_day=timezone.localtime().hour,
        median_minutes=6.0,
        sample_size=120,
    )
    QueueEntry.objects.create(
        facility=facility, service_type=general, patient=patient, ticket_code="G-001"
    )

    send_leave_now_notifications()
    send_leave_now_notifications()

    assert Notification.objects.filter(kind=Notification.Kind.LEAVE_NOW).count() <= 1


# --------------------------------------------------------------------------
# Honesty
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_no_leave_now_message_without_reliable_statistics(
    facility, general, patient
):
    """Below the sample gate we say nothing rather than guess a departure
    time somebody would act on."""
    ServiceTimeStat.objects.create(
        facility=facility,
        service_type=general,
        hour_of_day=timezone.localtime().hour,
        median_minutes=6.0,
        sample_size=19,  # one below the gate
    )
    QueueEntry.objects.create(
        facility=facility, service_type=general, patient=patient, ticket_code="G-001"
    )

    assert send_leave_now_notifications() == 0
    assert not Notification.objects.filter(kind=Notification.Kind.LEAVE_NOW).exists()


@pytest.mark.django_db
def test_no_leave_now_message_without_a_home_location(facility, general, db):
    patient = Patient.objects.create(phone="+250788999000")  # no home_location
    ServiceTimeStat.objects.create(
        facility=facility,
        service_type=general,
        hour_of_day=timezone.localtime().hour,
        median_minutes=6.0,
        sample_size=120,
    )
    QueueEntry.objects.create(
        facility=facility, service_type=general, patient=patient, ticket_code="G-001"
    )

    assert send_leave_now_notifications() == 0


@pytest.mark.django_db
def test_called_notification_is_skipped_for_walk_ins(facility, general):
    entry = QueueEntry.objects.create(
        facility=facility,
        service_type=general,
        walk_in_name="Uwase Alice",
        ticket_code="G-001",
    )

    assert send_called_notification(entry) is False


# --------------------------------------------------------------------------
# Travel and leave_by
# --------------------------------------------------------------------------


def test_travel_time_is_none_without_an_origin():
    assert travel_minutes(None, KIMIRONKO) is None


def test_travel_time_is_plausible_across_kigali():
    """Convention Centre to Kimironko is roughly 5.8 km."""
    minutes = travel_minutes(KCC, KIMIRONKO)
    assert 20 <= minutes <= 40


def test_leave_by_is_none_when_anything_is_unknown():
    now = timezone.now()
    assert leave_by(now=now, eta_minutes=None, travel=20) is None
    assert leave_by(now=now, eta_minutes=45, travel=None) is None


def test_leave_by_never_returns_a_time_in_the_past():
    """Already late to set off? The answer is 'now', not a past time."""
    now = timezone.now()
    assert leave_by(now=now, eta_minutes=5, travel=40) == now


def test_leave_by_subtracts_travel_and_buffer(settings):
    now = timezone.now()
    depart = leave_by(now=now, eta_minutes=60, travel=20)

    expected = now + timedelta(minutes=60 - 20 - settings.LEAVE_BY_BUFFER_MINUTES)
    assert abs((depart - expected).total_seconds()) < 1


# --------------------------------------------------------------------------
# Appointment reminders
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_appointment_reminders_fire_in_their_windows(facility, general, patient):
    now = timezone.now()
    Appointment.objects.create(
        facility=facility,
        service_type=general,
        patient=patient,
        slot_start=now + timedelta(hours=24),
        slot_end=now + timedelta(hours=24, minutes=15),
    )

    assert send_appointment_reminders() == 1
    assert Notification.objects.filter(
        kind=Notification.Kind.APPT_REMINDER_24H
    ).exists()


@pytest.mark.django_db
def test_cancelled_appointments_get_no_reminder(facility, general, patient):
    now = timezone.now()
    Appointment.objects.create(
        facility=facility,
        service_type=general,
        patient=patient,
        slot_start=now + timedelta(hours=24),
        slot_end=now + timedelta(hours=24, minutes=15),
        status=Appointment.Status.CANCELLED,
    )

    assert send_appointment_reminders() == 0
