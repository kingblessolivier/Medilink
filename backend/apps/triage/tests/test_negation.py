import pytest

from apps.triage.engine import check
from apps.triage.protocol import parse
from apps.triage.tests.test_check import PROTOCOL


@pytest.mark.parametrize("text", ["No fever but my tooth hurts", "Without fever. My tooth hurts", "Pas de fievre mais mal a la dent", "Sinfite umuriro ariko iryinyo rirababaza"])
def test_explicitly_denied_fever_does_not_rank(text):
    result = check(parse(PROTOCOL, source="test"), text)
    assert [item.code for item in result.conditions] == ["dental_problem"]


@pytest.mark.parametrize("text", ["No fever and I cannot breathe", "I cannot breathe", "Je ne peux pas respirer"])
def test_intrinsically_negative_danger_phrase_is_preserved(text):
    result = check(parse(PROTOCOL, source="test"), text)
    assert result.escalate
