"""Notification preferences.

The right to object, from docs/08 section 7. Two properties matter: an opt-out
is honoured by the SENDER so no call site can forget it, and transactional
messages cannot be switched off at all.
"""

from datetime import time

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient

from apps.facilities.models import Facility, OpeningHours, ServiceType
from apps.notifications.models import (
    OPTIONAL_KINDS,
    Notification,
    NotificationPreference,
)
from apps.notifications.services import dispatch
from apps.patients.auth import tokens_for_patient
from apps.patients.models import Patient
from apps.queueing.models import QueueEntry

PREFERENCES = "/api/v1/me/notification-preferences"
HISTORY = "/api/v1/me/notifications"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def patient(db):
    return Patient.objects.create(phone="+250788111222")


@pytest.fixture
def general(db):
    return ServiceType.objects.create(
        code="general_consultation", name_en="General", name_rw="x", name_fr="x"
    )


@pytest.fixture
def facility(db):
    facility = Facility.objects.create(
        name="Kimironko HC", slug="kimironko-hc", ownership="public",
        level="health_centre", district="Gasabo",
        location=Point(30.1122, -1.9481, srid=4326),
        verified_at=timezone.now(), reports_queue=True,
    )
    for weekday in range(7):
        OpeningHours.objects.create(
            facility=facility, weekday=weekday, opens_at=time(0, 0),
            closes_at=time(23, 59),
        )
    return facility


def authed(client, patient):
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + tokens_for_patient(patient)["access"]
    )
    return client


def prefs(body):
    return {p["kind"]: p for p in body["results"]}


# --------------------------------------------------------------------------
# Honoured by the sender
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_an_opt_out_stops_the_message(patient, facility, general):
    """Checked inside dispatch(), so no call site can forget it."""
    entry = QueueEntry.objects.create(
        facility=facility, service_type=general, patient=patient, ticket_code="G-1"
    )
    NotificationPreference.objects.create(
        patient=patient, kind=Notification.Kind.LEAVE_NOW, enabled=False
    )

    result = dispatch(
        kind=Notification.Kind.LEAVE_NOW,
        phone=patient.phone,
        patient=patient,
        queue_entry=entry,
        position=3,
        facility="Kimironko HC",
    )

    assert result is None
    assert Notification.objects.count() == 0


@pytest.mark.django_db
def test_absence_of_a_row_means_enabled(patient, facility, general):
    """Rows exist only for opt-outs, which keeps the default obvious."""
    entry = QueueEntry.objects.create(
        facility=facility, service_type=general, patient=patient, ticket_code="G-1"
    )

    assert dispatch(
        kind=Notification.Kind.LEAVE_NOW,
        phone=patient.phone,
        patient=patient,
        queue_entry=entry,
        position=3,
        facility="Kimironko HC",
    ) is not None


@pytest.mark.django_db
def test_a_transactional_message_ignores_an_opt_out(patient):
    """A sign-in code is not something a patient receives - it is something
    they asked for by trying to sign in."""
    NotificationPreference.objects.create(
        patient=patient, kind=Notification.Kind.OTP, enabled=False
    )

    assert dispatch(
        kind=Notification.Kind.OTP,
        phone=patient.phone,
        patient=patient,
        code="123456",
        minutes=5,
    ) is not None


@pytest.mark.django_db
def test_a_facility_cancelling_always_reaches_the_patient(patient):
    """Not telling somebody their appointment was cancelled is worse than any
    amount of unwanted messaging."""
    assert Notification.Kind.APPT_CANCELLED not in OPTIONAL_KINDS


# --------------------------------------------------------------------------
# The API
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_preferences_default_to_on(api_client, patient):
    authed(api_client, patient)

    found = prefs(api_client.get(PREFERENCES).json())

    assert all(p["enabled"] for p in found.values())


@pytest.mark.django_db
def test_transactional_kinds_are_marked_undisableable(api_client, patient):
    """The UI renders these as fixed, not as a toggle that does nothing."""
    authed(api_client, patient)

    found = prefs(api_client.get(PREFERENCES).json())

    assert found[Notification.Kind.APPT_CANCELLED]["can_disable"] is False
    assert found[Notification.Kind.LEAVE_NOW]["can_disable"] is True


@pytest.mark.django_db
def test_turning_one_off(api_client, patient):
    authed(api_client, patient)

    body = api_client.patch(
        PREFERENCES,
        {"kind": Notification.Kind.LEAVE_NOW, "enabled": False},
        format="json",
    ).json()

    assert prefs(body)[Notification.Kind.LEAVE_NOW]["enabled"] is False
    # And it survives a reload.
    assert prefs(api_client.get(PREFERENCES).json())[
        Notification.Kind.LEAVE_NOW
    ]["enabled"] is False


@pytest.mark.django_db
def test_turning_it_back_on(api_client, patient):
    authed(api_client, patient)
    api_client.patch(
        PREFERENCES, {"kind": Notification.Kind.LEAVE_NOW, "enabled": False},
        format="json",
    )

    body = api_client.patch(
        PREFERENCES, {"kind": Notification.Kind.LEAVE_NOW, "enabled": True},
        format="json",
    ).json()

    assert prefs(body)[Notification.Kind.LEAVE_NOW]["enabled"] is True


@pytest.mark.django_db
def test_switching_off_a_transactional_kind_is_refused(api_client, patient):
    """Refused rather than silently ignored: a toggle that appears to work and
    does nothing is worse than one that says no."""
    authed(api_client, patient)

    response = api_client.patch(
        PREFERENCES,
        {"kind": Notification.Kind.APPT_CANCELLED, "enabled": False},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["field"] == "kind"


# --------------------------------------------------------------------------
# History
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_history_shows_only_what_was_actually_sent(api_client, patient):
    """A queued-but-failed message is an operational problem, not something to
    show a patient as received."""
    Notification.objects.create(
        patient=patient, phone=patient.phone, channel="sms",
        kind=Notification.Kind.CALLED, body="sent", sent_at=timezone.now(),
    )
    Notification.objects.create(
        patient=patient, phone=patient.phone, channel="sms",
        kind=Notification.Kind.APPT_REMINDER_2H, body="failed",
        failed_at=timezone.now(),
    )

    body = api_client.get(HISTORY, **{"HTTP_AUTHORIZATION": "Bearer " + tokens_for_patient(patient)["access"]}).json()

    assert body["count"] == 1
    assert body["results"][0]["body"] == "sent"


@pytest.mark.django_db
def test_history_never_lists_sign_in_codes(api_client, patient):
    """A code is not a message somebody received; it is one they asked for.
    Listing it would also leave the code readable long after it expired."""
    Notification.objects.create(
        patient=patient, phone=patient.phone, channel="sms",
        kind=Notification.Kind.OTP, body="code 123456", sent_at=timezone.now(),
    )
    authed(api_client, patient)

    assert api_client.get(HISTORY).json()["count"] == 0


@pytest.mark.django_db
def test_history_is_scoped_to_the_caller(api_client, patient, db):
    other = Patient.objects.create(phone="+250788999000")
    Notification.objects.create(
        patient=other, phone=other.phone, channel="sms",
        kind=Notification.Kind.CALLED, body="theirs", sent_at=timezone.now(),
    )
    authed(api_client, patient)

    assert api_client.get(HISTORY).json()["count"] == 0


@pytest.mark.django_db
def test_anonymous_callers_are_refused(api_client):
    for path in (HISTORY, PREFERENCES):
        assert api_client.get(path).status_code in (401, 403)
