from django.contrib import admin

from .models import TriageOutcome


@admin.register(TriageOutcome)
class TriageOutcomeAdmin(admin.ModelAdmin):
    list_display = [
        "date",
        "hour_bucket",
        "protocol_version",
        "recommended_service",
        "escalated_emergency",
        "questions_answered",
    ]
    list_filter = ["protocol_version", "escalated_emergency", "recommended_service"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # An aggregate record of what the protocol did. Editing it would make
        # the protocol review meaningless.
        return False
