from django.contrib import admin

from .models import StaffMember


@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ["user", "facility", "role", "active"]
    list_filter = ["role", "active", "facility__district"]
    search_fields = ["user__username", "facility__name"]
    autocomplete_fields = ["facility"]
