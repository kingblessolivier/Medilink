"""USSD session state.

The `text` field carries the full input path, so short flows need no state at
all. Anything that maps a menu number back to a database row - a facility list,
a slot list - is cached here instead, because re-deriving it from the path is
slow and unreadable.

TTL is deliberately longer than any real session: a stale key costs nothing,
an expired one mid-flow costs the patient their whole session.
"""

import json

from django.core.cache import cache

TTL_SECONDS = 180
PREFIX = "ussd:"


def get_state(session_id: str) -> dict:
    raw = cache.get(PREFIX + session_id)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {}


def set_state(session_id: str, state: dict) -> None:
    cache.set(PREFIX + session_id, json.dumps(state), TTL_SECONDS)


def clear_state(session_id: str) -> None:
    cache.delete(PREFIX + session_id)
