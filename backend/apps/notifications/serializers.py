from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """What was sent to this patient. Read-only: a notification is a record of
    something that happened, never something a client authors."""

    kind_label = serializers.SerializerMethodField()
    id = serializers.IntegerField(read_only=True)
    kind = serializers.CharField(read_only=True)
    channel = serializers.CharField(read_only=True)
    body = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    sent_at = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = ["id", "kind", "kind_label", "channel", "body", "created_at", "sent_at"]

    def get_kind_label(self, obj) -> str:
        return obj.get_kind_display()


class NotificationListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = NotificationSerializer(many=True)


class PreferenceSerializer(serializers.Serializer):
    kind = serializers.CharField()
    label = serializers.CharField()
    enabled = serializers.BooleanField()
    # False for transactional messages - sign-in codes and a facility
    # cancelling on you. The UI renders these as fixed, not as a broken toggle.
    can_disable = serializers.BooleanField()


class PreferenceListSerializer(serializers.Serializer):
    results = PreferenceSerializer(many=True)


class PreferenceUpdateSerializer(serializers.Serializer):
    kind = serializers.CharField(max_length=24)
    enabled = serializers.BooleanField()
