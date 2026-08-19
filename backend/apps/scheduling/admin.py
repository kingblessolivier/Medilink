from django.contrib import admin

from .models import Appointment, ScheduleTemplate


@admin.register(ScheduleTemplate)
class ScheduleTemplateAdmin(admin.ModelAdmin):
    list_display = [
        "facility",
        "service_type",
        "weekday",
        "start_time",
        "end_time",
        "slot_minutes",
        "capacity_per_slot",
        "active",
    ]
    list_filter = ["facility", "service_type", "weekday", "active"]
    autocomplete_fields = ["facility"]


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "facility",
        "service_type",
        "patient",
        "slot_start",
        "status",
    ]
    list_filter = ["status", "facility", "service_type"]
    search_fields = ["reference", "patient__phone"]
    autocomplete_fields = ["facility", "patient"]
    readonly_fields = ["created_at", "cancelled_at", "reference"]
