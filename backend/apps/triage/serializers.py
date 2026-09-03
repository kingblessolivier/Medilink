from rest_framework import serializers


class TranslationSerializer(serializers.Serializer):
    rw = serializers.CharField()
    en = serializers.CharField()
    fr = serializers.CharField()


class TriageStatusSerializer(serializers.Serializer):
    available = serializers.BooleanField()
    protocol_version = serializers.CharField(allow_blank=True)
    approved_by = serializers.CharField(allow_blank=True)
    approved_on = serializers.CharField(allow_blank=True)
    reason = serializers.CharField(allow_blank=True)


class StartSessionSerializer(serializers.Serializer):
    """Optional free text describing how the patient feels.

    Capped hard. This is matched against a phrase list and then discarded, so
    there is no reason to accept an essay - and an unbounded field that is
    normalised character by character is a cheap way to burn CPU on a public
    endpoint.
    """

    symptom_text = serializers.CharField(
        required=False, allow_blank=True, max_length=300, trim_whitespace=True
    )


class TriageOptionSerializer(serializers.Serializer):
    code = serializers.CharField()
    text = TranslationSerializer()


class TriageQuestionSerializer(serializers.Serializer):
    code = serializers.CharField()
    red_flag = serializers.BooleanField()
    text = TranslationSerializer()
    options = TriageOptionSerializer(many=True)


class RankedConditionSerializer(serializers.Serializer):
    """One condition the answers pointed at.

    `share` is this condition's portion of the total matched score, 0..1. It
    is NOT a probability of having the condition, and the field is named for
    what it is so a client cannot honestly render it as one.
    """

    code = serializers.CharField()
    names = TranslationSerializer()
    advice = TranslationSerializer(allow_null=True)
    share = serializers.FloatField()


class TriageSessionSerializer(serializers.Serializer):
    session_id = serializers.CharField()
    protocol_version = serializers.CharField()
    approved_by = serializers.CharField()
    # Shown on EVERY response, not once at onboarding.
    disclaimer = TranslationSerializer()
    # When true the client must abandon the flow and show emergency guidance
    # immediately. This is a hard client requirement, not a suggestion.
    escalate_emergency = serializers.BooleanField()
    emergency_advice = TranslationSerializer(allow_null=True)
    recommendation = serializers.CharField(allow_null=True)
    # Ranked conditions, most-supported first. Empty unless the signed
    # protocol declares conditions AND the session has not escalated.
    conditions = RankedConditionSerializer(many=True)
    finished = serializers.BooleanField()
    next_question = TriageQuestionSerializer(allow_null=True)


class AnswerSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=64)
    option = serializers.CharField(max_length=64)


class CheckRequestSerializer(serializers.Serializer):
    """What a patient typed. Never stored - matched, then dropped."""

    text = serializers.CharField(max_length=300, allow_blank=False, trim_whitespace=True)


class CheckResultSerializer(serializers.Serializer):
    """The whole answer, in one response.

    `matched` distinguishes "we recognised nothing you said" from "we
    recognised it and it points nowhere". Collapsing those two would let an
    empty result read as a clean bill of health.
    """

    protocol_version = serializers.CharField()
    approved_by = serializers.CharField()
    disclaimer = TranslationSerializer()
    escalate_emergency = serializers.BooleanField()
    emergency_advice = TranslationSerializer(allow_null=True)
    conditions = RankedConditionSerializer(many=True)
    recommendation = serializers.CharField(allow_null=True)
    matched = serializers.BooleanField()
