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


# --------------------------------------------------------------------------
# Booking a named clinician
# --------------------------------------------------------------------------


@pytest.fixture
def doctor(db, facility, general):
    from apps.providers.models import Provider, ProviderFacility

    provider = Provider.objects.create(slug="dr-uwase", full_name="Uwase Alice")
    placement = ProviderFacility.objects.create(provider=provider, facility=facility)
    placement.service_types.set([general])
    return provider


@pytest.fixture
def doctor_clinic(facility, general, doctor):
    """That clinician's own session - a separate list from the general clinic."""
    for weekday in range(7):
        ScheduleTemplate.objects.create(
            facility=facility,
            service_type=general,
            provider=doctor,
            weekday=weekday,
            start_time=time(14, 0),
            end_time=time(16, 0),
            slot_minutes=20,
            capacity_per_slot=1,
        )


@pytest.mark.django_db
def test_general_clinic_slots_exclude_a_clinicians_own_session(
    facility, general, templates, doctor_clinic
):
    """"Any available" means the facility's general clinic, not every list in
    the building."""
    days = available_slots(facility=facility, service_type=general)
    starts = {s["start"].hour for day in days for s in day["slots"]}

    assert 8 in starts  # the general clinic runs 08:00-12:00
    assert 14 not in starts  # the doctor's own 14:00 session is not offered


@pytest.mark.django_db
def test_naming_a_clinician_returns_their_own_list(
    facility, general, templates, doctor, doctor_clinic
):
    days = available_slots(facility=facility, service_type=general, provider=doctor)
    starts = {s["start"].hour for day in days for s in day["slots"]}

    assert starts <= {14, 15}


@pytest.mark.django_db
def test_the_two_lists_are_separate_capacity_pools(
    facility, general, templates, doctor, doctor_clinic, patient, other_patient
):
    """A booking on the general clinic must not consume the doctor's slot, or
    a full waiting room would silently close every clinician's list."""
    slot = tomorrow_at(14)

    book(
        facility=facility,
        service_type=general,
        patient=patient,
        slot_start=slot,
        provider=doctor,
    )

    # The doctor's only seat at 14:00 is gone...
    days = available_slots(facility=facility, service_type=general, provider=doctor)
    taken = next(
        s for day in days for s in day["slots"] if s["start"] == slot
    )
    assert taken["remaining"] == 0

    # ...but the general clinic is untouched.
    general_days = available_slots(facility=facility, service_type=general)
    assert all(
        s["remaining"] == 2 for day in general_days for s in day["slots"]
    )


@pytest.mark.django_db
def test_a_slot_from_the_wrong_list_is_rejected(
    facility, general, templates, doctor, doctor_clinic, patient
):
    """08:00 belongs to the general clinic; it is not on the doctor's grid."""
    with pytest.raises(BookingError, match="does not offer that time"):
        book(
            facility=facility,
            service_type=general,
            patient=patient,
            slot_start=tomorrow_at(8),
            provider=doctor,
        )


@pytest.mark.django_db
def test_the_appointment_records_who(
    facility, general, templates, doctor, doctor_clinic, patient
):
    appointment = book(
        facility=facility,
        service_type=general,
        patient=patient,
        slot_start=tomorrow_at(14),
        provider=doctor,
    )

    assert appointment.provider_id == doctor.pk


@pytest.mark.django_db
def test_any_available_records_no_clinician(
    facility, general, templates, patient
):
    """The default. Naming a doctor narrows availability and most patients do
    not need to."""
    appointment = book(
        facility=facility,
        service_type=general,
        patient=patient,
        slot_start=tomorrow_at(8),
    )

    assert appointment.provider_id is None


@pytest.mark.django_db
def test_booking_endpoint_accepts_a_provider(
    api_client, facility, general, templates, doctor, doctor_clinic, patient
):
    authed(api_client, patient)

    response = api_client.post(
        "/api/v1/appointments",
        {
            "facility": facility.slug,
            "service": general.code,
            "provider": doctor.slug,
            "slot_start": tomorrow_at(14).isoformat(),
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["provider"] == "Dr Uwase Alice"


@pytest.mark.django_db
def test_slots_endpoint_echoes_the_provider(
    api_client, facility, general, templates, doctor, doctor_clinic
):
    body = api_client.get(
        f"/api/v1/facilities/{facility.slug}/slots",
        {"service": general.code, "provider": doctor.slug},
    ).json()

    assert body["provider"] == doctor.slug
    hours = {int(s["start"][11:13]) for day in body["days"] for s in day["slots"]}
    assert hours <= {14, 15}


@pytest.mark.django_db
def test_appointment_detail_is_scoped_to_the_caller(
    api_client, facility, general, templates, patient, other_patient
):
    """An enumerated id must not reveal somebody else's appointment."""
    theirs = book(
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

    assert api_client.get(f"/api/v1/appointments/{mine.id}").status_code == 200
    assert api_client.get(f"/api/v1/appointments/{theirs.id}").status_code == 404


@pytest.mark.django_db
def test_appointment_detail_carries_the_reference(
    api_client, facility, general, templates, patient
):
    """The code a patient reads aloud at a reception desk."""
    appointment = book(
        facility=facility,
        service_type=general,
        patient=patient,
        slot_start=tomorrow_at(8),
    )
    authed(api_client, patient)

    body = api_client.get(f"/api/v1/appointments/{appointment.id}").json()

    assert body["reference"] == appointment.reference
    assert body["provider"] is None  # "any available"


# --------------------------------------------------------------------------
# Concurrency - the guarantee book() claims to make
# --------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_two_patients_cannot_both_take_the_last_slot(facility, general):
    """Real threads, real transactions, one slot.

    `book()` documented this guarantee and did not provide it. It took
    `select_for_update()` on the appointments themselves, which reads
    correctly and locks nothing: with capacity 1 and nothing booked the
    filter matches no rows, and PostgreSQL has no gap lock to take. Both
    callers counted zero and both inserted.

    The partial unique constraint does not cover it either - it is keyed on
    `patient`, so it stops one person double-tapping and permits exactly this.

    Needs `transaction=True`: the usual wrapped-transaction fixture would make
    the two threads invisible to each other and the test would pass either way.
    """
    import threading

    from django.db import connection

    ScheduleTemplate.objects.create(
        facility=facility,
        service_type=general,
        weekday=(timezone.localtime() + timedelta(days=1)).weekday(),
        start_time=time(9, 0),
        end_time=time(10, 0),
        slot_minutes=15,
        capacity_per_slot=1,  # the last slot, by construction
    )
    slot = tomorrow_at(9, 0)

    first = Patient.objects.create(phone="+250788900001")
    second = Patient.objects.create(phone="+250788900002")

    ready = threading.Barrier(2, timeout=10)
    outcomes: list[str] = []
    lock = threading.Lock()

    def attempt(who):
        try:
            ready.wait()
            book(
                facility=facility,
                service_type=general,
                patient=who,
                slot_start=slot,
            )
            result = "booked"
        except SlotUnavailable:
            result = "refused"
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            result = f"error:{type(exc).__name__}"
        finally:
            connection.close()  # each thread holds its own
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=attempt, args=(p,)) for p in (first, second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert sorted(outcomes) == ["booked", "refused"]
    assert Appointment.objects.filter(slot_start=slot).count() == 1


@pytest.mark.django_db(transaction=True)
def test_a_named_clinician_and_the_general_clinic_do_not_block_each_other(
    facility, general, patient, other_patient
):
    """Separate capacity pools must stay separate.

    Serialising on the template is the fix for the race above, and the risk of
    a coarse lock is that it also serialises bookings that were never in
    competition. Dr A's 09:00 and the general clinic's 09:00 are different
    appointments and have their own templates, so both still succeed.
    """
    from apps.providers.models import Provider

    weekday = (timezone.localtime() + timedelta(days=1)).weekday()
    provider = Provider.objects.create(full_name="Dr Uwase Alice", slug="dr-uwase")

    for owner in (None, provider):
        ScheduleTemplate.objects.create(
            facility=facility,
            service_type=general,
            provider=owner,
            weekday=weekday,
            start_time=time(9, 0),
            end_time=time(10, 0),
            slot_minutes=15,
            capacity_per_slot=1,
        )

    slot = tomorrow_at(9, 0)
    book(facility=facility, service_type=general, patient=patient, slot_start=slot)
    book(
        facility=facility,
        service_type=general,
        patient=other_patient,
        slot_start=slot,
        provider=provider,
    )

    assert Appointment.objects.filter(slot_start=slot).count() == 2


@pytest.mark.django_db
def test_duplicate_general_clinic_sessions_are_refused_at_the_database(
    facility, general
):
    """The case `unique_together` silently missed.

    It listed `provider`, and SQL compares NULL to NULL as NOT EQUAL - so a
    named clinician's list was protected and the GENERAL CLINIC, where
    provider is NULL, was not. That is the default and the common case.

    Two identical templates put the same 09:00 in the list twice and leave
    `_template_for` picking between them arbitrarily.
    """
    from django.db import IntegrityError

    from apps.scheduling.models import ScheduleTemplate

    fields = dict(
        facility=facility,
        service_type=general,
        provider=None,
        weekday=1,
        start_time=time(8, 0),
        end_time=time(12, 0),
    )
    ScheduleTemplate.objects.create(**fields)

    with pytest.raises(IntegrityError):
        ScheduleTemplate.objects.create(**fields)
