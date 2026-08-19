"""Travel time, and the sentence the whole product exists for.

    "You are number 8. Leave home by 10:15."

We do not do routing - that would mean a paid directions API and a network call
on the hottest endpoint in the system. A straight-line distance with a detour
factor is accurate enough to tell somebody when to set off, and it degrades
honestly: when we cannot compute it, the UI hides the line rather than guessing.

Every rounding here is deliberately CONSERVATIVE. Telling a patient to leave too
late is far worse than telling them to leave too early: too early costs them a
few minutes in a waiting room, too late costs them their place in the queue.
"""

import math
from datetime import timedelta

from django.conf import settings

EARTH_RADIUS_M = 6_371_000

# Straight line under-states real travel. Kigali roads wind around hills, so
# actual distance runs roughly 40% above the crow-flies figure.
DETOUR_FACTOR = 1.4

# Effective door-to-door speed including walking to a moto, waiting for it, and
# traffic. Deliberately pessimistic.
AVERAGE_SPEED_KMH = 16.0

MIN_TRAVEL_MINUTES = 5


def haversine_metres(lat1, lng1, lat2, lng2) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def travel_minutes(origin, destination) -> int | None:
    """Minutes from origin to destination, or None if origin is unknown.

    `origin` and `destination` are Point objects (x = longitude, y = latitude).
    """
    if origin is None or destination is None:
        return None

    metres = haversine_metres(origin.y, origin.x, destination.y, destination.x)
    road_km = (metres * DETOUR_FACTOR) / 1000
    minutes = (road_km / AVERAGE_SPEED_KMH) * 60
    return max(MIN_TRAVEL_MINUTES, math.ceil(minutes))


def leave_by(*, now, eta_minutes: int | None, travel: int | None):
    """When the patient should set off, or None if we cannot say.

    Returning None is a real answer: the client hides the line entirely rather
    than showing a placeholder time somebody might act on.
    """
    if eta_minutes is None or travel is None:
        return None

    buffer_minutes = getattr(settings, "LEAVE_BY_BUFFER_MINUTES", 10)
    depart = now + timedelta(minutes=eta_minutes - travel - buffer_minutes)
    # Already late to set off? Then the answer is "now", never a past time.
    return max(depart, now)
