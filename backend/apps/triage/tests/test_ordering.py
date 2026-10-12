import pytest

from apps.triage import engine
from apps.triage.protocol import parse
from apps.triage.tests.test_engine import protocol_dict


def test_a_routing_answer_cannot_skip_emergency_screening():
    protocol = parse(protocol_dict())
    state = engine.SessionState("test", protocol.version, {}, [])
    with pytest.raises(engine.TriageError, match="current question"):
        engine.answer(protocol, state, "route", "a")
    assert not state.finished
    assert state.answers == {}


def test_a_session_cannot_answer_against_a_different_protocol():
    protocol = parse(protocol_dict())
    state = engine.SessionState("test", "previous-version", {}, [])
    with pytest.raises(engine.TriageError, match="protocol changed"):
        engine.answer(protocol, state, "red", "no")
    assert state.answers == {}
