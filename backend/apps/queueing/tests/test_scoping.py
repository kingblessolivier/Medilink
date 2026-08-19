"""Facility scoping - the leak test.

One forgotten .filter() exposes another clinic's patient list, and that is the
breach that ends the project. This file is parametrised over every staff
endpoint so that a newly added endpoint which is not covered is obvious in
review.
"""

import pytest

# (method, path template). Add every new staff endpoint here.
STAFF_ENDPOINTS = [
    ("get", "/api/v1/queue/board"),
    ("post", "/api/v1/queue/entries/{entry_id}/call"),
    ("post", "/api/v1/queue/entries/{entry_id}/serve"),
    ("post", "/api/v1/queue/entries/{entry_id}/skip"),
    ("post", "/api/v1/queue/entries/{entry_id}/cancel"),
    ("get", "/api/v1/staff/me"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("method,path", STAFF_ENDPOINTS)
def test_anonymous_callers_are_rejected(api_client, method, path, facility, general,
                                        make_entry):
    entry = make_entry(facility, general)
    response = getattr(api_client, method)(path.format(entry_id=entry.id))

    assert response.status_code in (401, 403)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/v1/queue/entries/{entry_id}/call"),
        ("post", "/api/v1/queue/entries/{entry_id}/serve"),
        ("post", "/api/v1/queue/entries/{entry_id}/skip"),
        ("post", "/api/v1/queue/entries/{entry_id}/cancel"),
    ],
)
def test_staff_cannot_touch_another_facilitys_entries(
    api_client, other_receptionist, facility, general, make_entry, method, path
):
    """Reception at facility B must not reach an entry at facility A.

    404 rather than 403, so an enumerated id does not confirm it exists.
    """
    entry = make_entry(facility, general)
    api_client.force_authenticate(other_receptionist)

    response = getattr(api_client, method)(path.format(entry_id=entry.id))

    assert response.status_code == 404


@pytest.mark.django_db
def test_board_shows_only_the_callers_own_facility(
    staff_client, facility, other_facility, general, make_entry
):
    make_entry(facility, general, name="Ours")
    make_entry(other_facility, general, name="Theirs")

    body = staff_client.get("/api/v1/queue/board").json()

    names = [
        row["display_name"]
        for service in body["services"]
        for row in service["waiting"]
    ]
    assert names == ["Ours"]
    assert body["facility"]["slug"] == facility.slug


@pytest.mark.django_db
def test_check_in_ignores_any_facility_sent_by_the_client(
    staff_client, facility, other_facility, general
):
    """facility is derived from the staff member, never from the payload."""
    response = staff_client.post(
        "/api/v1/queue/entries",
        {
            "service": general.code,
            "walk_in_name": "Uwase",
            "facility": other_facility.id,
        },
        format="json",
    )

    assert response.status_code == 201

    from apps.queueing.models import QueueEntry

    assert QueueEntry.objects.get().facility_id == facility.id


@pytest.mark.django_db
def test_clinicians_can_read_but_not_mutate(
    api_client, clinician, facility, general, make_entry
):
    entry = make_entry(facility, general)
    api_client.force_authenticate(clinician)

    assert api_client.get("/api/v1/queue/board").status_code == 200
    assert (
        api_client.post(f"/api/v1/queue/entries/{entry.id}/serve").status_code == 403
    )


@pytest.mark.django_db
def test_deactivated_staff_lose_access(api_client, receptionist, facility):
    receptionist.staffmember.active = False
    receptionist.staffmember.save()
    api_client.force_authenticate(receptionist)

    assert api_client.get("/api/v1/queue/board").status_code == 403


@pytest.mark.django_db
def test_authenticated_user_without_a_staff_record_is_rejected(api_client, db):
    from django.contrib.auth.models import User

    user = User.objects.create_user(username="nobody", password="test-pass-123")
    api_client.force_authenticate(user)

    assert api_client.get("/api/v1/queue/board").status_code == 403


@pytest.mark.django_db
def test_no_full_phone_number_anywhere_on_the_board(staff_client, facility, general):
    """A queue board is readable across a reception desk; a full number on
    screen is a needless disclosure.

    Asserted over the whole serialised payload, not just the phone field -
    masking `phone` while echoing the same number through `display_name` would
    defeat the point.
    """
    staff_client.post(
        "/api/v1/queue/entries",
        {"service": general.code, "phone": "+250788123456"},
        format="json",
    )

    response = staff_client.get("/api/v1/queue/board")
    row = response.json()["services"][0]["waiting"][0]

    assert row["phone"] == "+25078...456"
    assert row["display_name"] == "+25078...456"
    assert "+250788123456" not in response.content.decode()
