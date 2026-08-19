from django.contrib import admin

from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ["phone", "full_name", "language", "insurer", "last_seen_at"]
    search_fields = ["phone", "full_name"]
    list_filter = ["language", "insurer"]
    readonly_fields = ["created_at", "last_seen_at", "national_id_hash"]
