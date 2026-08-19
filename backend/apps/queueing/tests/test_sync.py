"""Offline reconciliation.

Reception check-in is the one operation that may never fail. These tests cover
what happens when the network returns.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.queueing.models import QueueEntry

SYNC = "/api/v1/queue/sync"


def action(key, kind, *, minutes_ago, payload):
    return {
        "key": key,
        "type": kind,
        "client_recorded_at": (
            timezone.now() - timedelta(minutes=minutes_ago)
        ).isoformat(),
        "payload": payload,
    }


@pytest.mark.django_db
def test_offline_check_ins_keep_the_receptionists_own_order(
    staff_client, facility, general
):
    """A receptionist offline for ten minutes must not push their patients
    behind everyone checked in since."""
    online_entry = staff_client.post(
        "/api/v1/queue/entries",
        {"service": general.code, "walk_in_name": "Checked in online"},
        format="json",
    ).json()

    response = staff_client.post(
        SYNC,
        {
            "actions": [
                action(
                    "k1",
                    "check_in",
                    minutes_ago=20,
                    payload={"service": general.code, "walk_in_name": "Offline early"},
                ),
                action(
                    "k2",
                    "check_in",
                    minutes_ago=15,
                    payload={"service": general.code, "walk_in_name": "Offline later"},
                ),
            ]
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["applied"] == 2

    order = list(
        QueueEntry.objects.order_by("joined_at").values_list("walk_in_name", flat=True)
    )
    assert order == ["Offline early", "Offline later", "Checked in online"]

    # And the online patient is now third, not first.
    assert QueueEntry.objects.get(pk=online_entry["id"]).position() == 3


@pytest.mark.django_db
def test_sync_applies_actions_in_client_timestamp_order(
    staff_client, facility, general
):
    """Actions may arrive shuffled; the server sorts by the client clock."""
    response = staff_client.post(
        SYNC,
        {
            "actions": [
                action(
                    "late",
                    "check_in",
                    minutes_ago=5,
                    payload={"service": general.code, "walk_in_name": "Second"},
                ),
                action(
                    "early",
                    "check_in",
                    minutes_ago=25,
                    payload={"service": general.code, "walk_in_name": "First"},
                ),
            ]
        },
        format="json",
    )

    assert response.json()["applied"] == 2
    order = list(
        QueueEntry.objects.order_by("joined_at").values_list("walk_in_name", flat=True)
    )
    assert order == ["First", "Second"]


@pytest.mark.django_db
def test_one_rejected_action_does_not_fail_the_batch(
    staff_client, facility, general
):
    """A receptionist reconnecting after an hour must not lose 39 good
    check-ins because one was a duplicate."""
    payload = {"service": general.code, "phone": "+250788123456"}
    response = staff_client.post(
        SYNC,
        {
            "actions": [
                action("a", "check_in", minutes_ago=30, payload=payload),
                action("b", "check_in", minutes_ago=20, payload=payload),  # duplicate
                action(
                    "c",
                    "check_in",
                    minutes_ago=10,
                    payload={"service": general.code, "walk_in_name": "Third"},
                ),
            ]
        },
        format="json",
    )

    body = response.json()
    assert body["applied"] == 2
    assert body["rejected"] == 1

    by_key = {r["key"]: r for r in body["results"]}
    assert by_key["a"]["ok"] is True
    assert by_key["b"]["ok"] is False
    assert "already in the queue" in by_key["b"]["error"]
    assert by_key["c"]["ok"] is True


@pytest.mark.django_db
def test_replaying_the_same_batch_creates_nothing_new(
    staff_client, facility, general
):
    """The client may retry a whole batch if the response was lost."""
    batch = {
        "actions": [
            action(
                "stable-key",
                "check_in",
                minutes_ago=10,
                payload={"service": general.code, "walk_in_name": "Uwase"},
            )
        ]
    }

    first = staff_client.post(SYNC, batch, format="json").json()
    second = staff_client.post(SYNC, batch, format="json").json()

    assert first["results"][0]["created"] is True
    assert second["results"][0]["created"] is False
    assert QueueEntry.objects.count() == 1


@pytest.mark.django_db
def test_sync_can_replay_transitions(staff_client, facility, general, make_entry):
    entry = make_entry(facility, general)

    response = staff_client.post(
        SYNC,
        {
            "actions": [
                action("t1", "call", minutes_ago=10, payload={"entry_id": entry.id}),
                action("t2", "serve", minutes_ago=5, payload={"entry_id": entry.id}),
            ]
        },
        format="json",
    )

    assert response.json()["applied"] == 2
    entry.refresh_from_db()
    assert entry.status == QueueEntry.Status.SERVED


@pytest.mark.django_db
def test_sync_rejects_an_entry_from_another_facility(
    staff_client, other_facility, general, make_entry
):
    entry = make_entry(other_facility, general)

    response = staff_client.post(
        SYNC,
        {
            "actions": [
                action("t1", "serve", minutes_ago=5, payload={"entry_id": entry.id})
            ]
        },
        format="json",
    )

    body = response.json()
    assert body["rejected"] == 1
    assert body["results"][0]["ok"] is False


@pytest.mark.django_db
def test_check_in_endpoint_honours_the_idempotency_key_header(
    staff_client, facility, general
):
    payload = {"service": general.code, "walk_in_name": "Uwase"}

    first = staff_client.post(
        "/api/v1/queue/entries",
        payload,
        format="json",
        headers={"Idempotency-Key": "net-retry-1"},
    )
    second = staff_client.post(
        "/api/v1/queue/entries",
        payload,
        format="json",
        headers={"Idempotency-Key": "net-retry-1"},
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert QueueEntry.objects.count() == 1
