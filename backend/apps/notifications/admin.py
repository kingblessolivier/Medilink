from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["kind", "phone", "channel", "created_at", "sent_at", "failed_at"]
    list_filter = ["kind", "channel", "failed_at"]
    search_fields = ["phone", "body"]
    readonly_fields = [
        "patient",
        "phone",
        "channel",
        "kind",
        "body",
        "queue_entry",
        "appointment",
        "created_at",
        "sent_at",
        "failed_at",
        "error",
        "provider_ref",
    ]

    def has_add_permission(self, request):
        # Notifications are a record of what was sent, never hand-authored.
        return False
