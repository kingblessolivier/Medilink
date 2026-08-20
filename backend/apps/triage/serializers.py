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


class TriageOptionSerializer(serializers.Serializer):
    code = serializers.CharField()
    text = TranslationSerializer()


class TriageQuestionSerializer(serializers.Serializer):
    code = serializers.CharField()
    red_flag = serializers.BooleanField()
    text = TranslationSerializer()
    options = TriageOptionSerializer(many=True)


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
    finished = serializers.BooleanField()
    next_question = TriageQuestionSerializer(allow_null=True)


class AnswerSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=64)
    option = serializers.CharField(max_length=64)
