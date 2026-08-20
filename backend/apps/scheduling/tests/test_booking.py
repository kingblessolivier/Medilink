from datetime import date, datetime, time, timedelta

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient

from apps.facilities.models import Facility, OpeningHours, ServiceType
from apps.patients.auth import tokens_for_patient
from apps.patients.models import Patient
from apps.scheduling.models import Appointment, ScheduleTemplate
from apps.scheduling.services import (
    BookingError,
    SlotUnavailable,
    available_slots,
    book,
    cancel,
)


@pytest.fixture
def api_client():
    return APIClient()


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
        name="Kimironko HC",
        slug="kimironko-hc",
        ownership="public",
        level="health_centre",
        district="Gasabo",
        location=Point(30.1122, -1.9481, srid=4326),
        verified_at=timezone.now(),
    )
    for weekday in range(7):
        OpeningHours.objects.create(
            facility=facility, weekday=weekday, opens_at=time(0, 0),
            closes_at=time(23, 59),
        )
    return facility


@pytest.fixture
def templates(facility, general):
    """08:00-12:00 every weekday, 15-minute slots, two patients per slot."""
    for weekday in range(7):
        ScheduleTemplate.objects.create(
            facility=facility,
            service_type=general,
            weekday=weekday,
            start_time=time(8, 0),
            end_time=time(12, 0),
            slot_minutes=15,
            capacity_per_slot=2,
        )


@pytest.fixture
def patient(db):
    return Patient.objects.create(phone="+250788111222")


@pytest.fixture
def other_patient(db):
    return Patient.objects.create(phone="+250788333444")


def tomorrow_at(hour, minute=0):
    local = timezone.localtime() + timedelta(days=1)
    return timezone.make_aware(
        datetime.combine(local.date(), time(hour, minute))
    )


# --------------------------------------------------------------------------
# Slot generation
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_slots_are_expanded_from_the_template(facility, general, templates):
    days = available_slots(facility=facility, service_type=general)

    assert days
    # 08:00-12:00 in 15-minute steps is 16 slots.
    full_day = next(d for d in days if len(d["slots"]) == 16)
    assert full_day["slots"][0]["remaining"] == 2


@pytest.mark.django_db
def test_past_slots_are_never_offered(facility, general, templates):
    days = available_slots(facility=facility, service_type=general)
    now = timezone.localtime()

    for day in days:
        for slot in day["slots"]:
            assert slot["start"] > now


@pytest.mark.django_db
def test_full_slots_are_returned_not_omitted(
    facility, general, templates, patient, other_patient
):
    """A patient needs to see that a day is busy, not that it is empty."""
    slot = tomorrow_at(8)
    book(facility=facility, service_type=general, patient=patient, slot_start=slot)
    book(
        facility=facility,
        service_type=general,
        patient=other_patient,
        slot_start=slot,
    )

    days = available_slots(
        facility=facility,
        service_type=general,
        date_from=slot.date(),
        date_to=slot.date(),
    )
    first = days[0]["slots"][0]

    assert first["remaining"] == 0
    assert first["capacity"] == 2


@pytest.mark.django_db
def test_slot_query_is_a_fixed_number_of_queries(
    facility, general, templates, django_assert_max_num_queries
):
    """One query for the whole window, not one per day."""
    with django_assert_max_num_queries(3):
        available_slots(
            facility=facility,
            service_type=general,
            date_from=date.today(),
            date_to=date.today() + timedelta(days=14),
        )


# --------------------------------------------------------------------------
# Booking
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_booking_creates_a_readable_reference(facility, general, templates, patient):
    appointment = book(
        facility=facility,
        service_type=general,
        patient=patient,
        slot_start=tomorrow_at(8),
    )

    assert len(appointment.reference) == 6
    # Unambiguous over a phone line: no O/0, no I/1.
    assert not set(appointment.reference) & set("OI01")


@pytest.mark.django_db
def test_capacity_is_enforced(
    facility, general, templates, patient, other_patient, db
):
    slot = tomorrow_at(8)
    book(facility=facility, service_type=general, patient=patient, slot_start=slot)
    book(
        facility=facility, service_type=general, patient=other_patient, slot_start=slot
    )

    third = Patient.objects.create(phone="+250788555666")
    with pytest.raises(SlotUnavailable):
        book(
            facility=facility, service_type=general, patient=third, slot_start=slot
        )


@pytest.mark.django_db
def test_the_same_patient_cannot_double_book_one_slot(
    facility, general, templates, patient
):
    slot = tomorrow_at(8)
    book(facility=facility, service_type=general, patient=patient, slot_start=slot)

    with pytest.raises(SlotUnavailable):
        book(facility=facility, service_type=general, patient=patient, slot_start=slot)


@pytest.mark.django_db
def test_slots_off_the_template_grid_are_rejected(
    facility, general, templates, patient
):
    with pytest.raises(BookingError, match="does not offer that time"):
        book(
            facility=facility,
            service_type=general,
            patient=patient,
            slot_start=tomorrow_at(8, 7),  # not a 15-minute boundary
        )


@pytest.mark.django_db
def test_past_slots_cannot_be_booked(facility, general, templates, patient):
    with pytest.raises(BookingError, match="already passed"):
        book(
            facility=facility,
            service_type=general,
            patient=patient,
            slot_start=timezone.now() - timedelta(hours=1),
        )


@pytest.mark.django_db
def test_open_booking_cap(facility, general, templates, patient, settings):
    """One patient must not silently exhaust a small facility's week."""
    from apps.scheduling.services import MAX_OPEN_APPOINTMENTS_PER_PATIENT

    for index in range(MAX_OPEN_APPOINTMENTS_PER_PATIENT):
        book(
            facility=facility,
            service_type=general,
            patient=patient,
            slot_start=tomorrow_at(8, 15 * index),
        )

    with pytest.raises(BookingError, match="upcoming appointments"):
        book(
            facility=facility,
            service_type=general,
            patient=patient,
            slot_start=tomorrow_at(9),
        )


# --------------------------------------------------------------------------
# Cancellation
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_cancelling_frees_the_slot(
    facility, general, templates, patient, other_patient
):
    slot = tomorrow_at(8)
    first = book(
        facility=facility, service_type=general, patient=patient, slot_start=slot
    )
    book(
        facility=facility, service_type=general, patient=other_patient, slot_start=slot
    )

    cancel(first)

    third = Patient.objects.create(phone="+250788555666")
    assert book(
        facility=facility, service_type=general, patient=third, slot_start=slot
    )


@pytest.mark.django_db
def test_cannot_cancel_twice(facility, general, templates, patient):
    appointment = book(
        facility=facility,
        service_type=general,
        patient=patient,
        slot_start=tomorrow_at(8),
    )
    cancel(appointment)

    with pytest.raises(BookingError, match="already cancelled"):
        cancel(appointment)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------


def authed(client, patient):
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + tokens_for_patient(patient)["access"]
    )
    return client


@pytest.mark.django_db
def test_booking_endpoint(api_client, facility, general, templates, patient):
    authed(api_client, patient)
    slot = tomorrow_at(8)

    response = api_client.post(
        "/api/v1/appointments",
        {
            "facility": facility.slug,
            "service": general.code,
            "slot_start": slot.isoformat(),
        },
        format="json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "booked"
    assert body["facility"]["name"] == "Kimironko HC"


@pytest.mark.django_db
def test_booking_a_taken_slot_returns_409(
    api_client, facility, general, templates, patient, other_patient
):
    slot = tomorrow_at(8)
    for holder in (patient, other_patient):
        book(
            facility=facility, service_type=general, patient=holder, slot_start=slot
        )

    third = Patient.objects.create(phone="+250788555666")
    authed(api_client, third)

    response = api_client.post(
        "/api/v1/appointments",
        {
            "facility": facility.slug,
            "service": general.code,
            "slot_start": slot.isoformat(),
        },
        format="json",
    )

    assert response.status_code == 409
    assert response.json()["type"] == "conflict"


@pytest.mark.django_db
def test_a_patient_sees_only_their_own_appointments(
    api_client, facility, general, templates, patient, other_patient
):
    book(
        facility=facility,
        service_type=general,
        patient=other_patient,
        slot_start=tomorrow_at(8),
    )
    mine = book(
        facility=facility,
        service_type=general,
        patient=patient,
        slot_start=tomorrow_at(9),
    )

    authed(api_client, patient)
    body = api_client.get("/api/v1/appointments").json()

    assert [row["reference"] for row in body] == [mine.reference]


@pytest.mark.django_db
def test_a_patient_cannot_cancel_someone_elses_appointment(
    api_client, facility, general, templates, patient, other_patient
):
    theirs = book(
        facility=facility,
        service_type=general,
        patient=other_patient,
        slot_start=tomorrow_at(8),
    )

    authed(api_client, patient)
    response = api_client.post(f"/api/v1/appointments/{theirs.id}/cancel")

    assert response.status_code == 404
    theirs.refresh_from_db()
    assert theirs.status == Appointment.Status.BOOKED
