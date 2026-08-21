"""No patient identifiers in application logs.

docs/08 section 6 requires this to be asserted by a test rather than trusted
to discipline: "do not log phone numbers" is a rule somebody breaks at 2am
debugging a check-in that will not sync, and the number then sits in a log
aggregator with different retention and a different access list from the
database.
"""

import logging

import pytest

from config.logging import RedactPatientIdentifiers, scrub


@pytest.fixture
def redactor():
    return RedactPatientIdentifiers()


def emit(redactor, msg, *args, exc_text=None):
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg=msg, args=args or None, exc_info=None,
    )
    if exc_text:
        record.exc_text = exc_text
    redactor.filter(record)
    return record


# --------------------------------------------------------------------------
# Phone numbers - the identity in this product
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "number",
    [
        "+250788123456",
        "250788123456",
        "0788123456",
        "+250 788 123 456",
        "0788-123-456",
        "+250788999000",
    ],
)
def test_a_phone_number_never_survives(redactor, number):
    record = emit(redactor, f"check-in failed for {number}")

    assert number not in record.msg
    assert "[redacted]" in record.msg


def test_a_phone_number_in_the_arguments_is_scrubbed(redactor):
    """`logger.info("checked in %s", phone)` is the shape this actually takes
    in real code - the number is in args, not in the format string."""
    record = emit(redactor, "checked in %s", "+250788123456")

    assert "+250788123456" not in str(record.args)


def test_a_phone_number_in_a_traceback_is_scrubbed(redactor):
    """Where it most often ends up: an exception rendered with the payload
    that caused it."""
    record = emit(
        redactor,
        "boom",
        exc_text='Traceback...\n  phone="+250788123456"\nValueError',
    )

    assert "+250788123456" not in record.exc_text


def test_dict_arguments_are_scrubbed(redactor):
    record = emit(redactor, "%(event)s", {"event": "sms to +250788123456"})

    assert "+250788123456" not in str(record.args)


# --------------------------------------------------------------------------
# Long digit runs - national IDs, and phone formats the pattern misses
# --------------------------------------------------------------------------


def test_a_national_id_is_scrubbed(redactor):
    record = emit(redactor, "national id 1199680123456789 rejected")

    assert "1199680123456789" not in record.msg


# --------------------------------------------------------------------------
# What it must NOT do
# --------------------------------------------------------------------------


def test_the_record_is_kept_not_dropped(redactor):
    """Content is filtered, not records. Losing the line would lose the
    operational signal it existed for."""
    record = emit(redactor, "check-in failed for +250788123456")

    assert redactor.filter(record) is True
    assert "check-in failed" in record.msg


def test_ordinary_numbers_survive(redactor):
    """A queue position, a duration and an HTTP status are not identifiers,
    and redacting them would make the logs useless."""
    message = scrub("position 8, waited 25 min, returned 503 in 1240 ms")

    assert "8" in message
    assert "25" in message
    assert "503" in message
    assert "1240" in message


def test_a_non_string_message_does_not_crash(redactor):
    """logger.info(some_object) is legal and happens."""
    record = emit(redactor, {"not": "a string"})

    assert record.msg == {"not": "a string"}


def test_a_ticket_code_survives(redactor):
    """Ticket codes are read aloud across a reception desk. They identify a
    place in a queue, not a person, and they have to stay legible."""
    assert "G-104" in scrub("called G-104")
