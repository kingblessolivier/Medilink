from django.contrib import admin

from .models import QueueEntry, ServiceTimeStat


@admin.register(QueueEntry)
class QueueEntryAdmin(admin.ModelAdmin):
    list_display = [
        "ticket_code",
        "facility",
        "service_type",
        "display_name",
        "status",
        "joined_at",
        "served_at",
    ]
    list_filter = ["status", "facility", "service_type"]
    search_fields = ["ticket_code", "walk_in_name", "patient__phone"]
    readonly_fields = ["joined_at", "called_at", "served_at", "closed_at"]
    autocomplete_fields = ["facility", "patient"]


@admin.register(ServiceTimeStat)
class ServiceTimeStatAdmin(admin.ModelAdmin):
    list_display = [
        "facility",
        "service_type",
        "hour_of_day",
        "median_minutes_per_patient",
        "sample_size",
        "publishable",
        "updated_at",
    ]
    list_filter = ["facility", "service_type"]

    @admin.display(boolean=True, description="Shown to patients")
    def publishable(self, obj):
        from django.conf import settings

        return obj.sample_size >= settings.MIN_SERVICE_TIME_SAMPLES
