from django.contrib import admin

from .models import FacilityInsurer, Insurer


@admin.register(Insurer)
class InsurerAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_public", "sort_order", "facility_count"]
    search_fields = ["code", "name"]
    list_filter = ["is_public"]

    @admin.display(description="Facilities accepting")
    def facility_count(self, obj):
        return obj.facilityinsurer_set.count()


@admin.register(FacilityInsurer)
class FacilityInsurerAdmin(admin.ModelAdmin):
    list_display = ["facility", "insurer", "confirmed_at"]
    list_filter = ["insurer", "facility__district"]
    search_fields = ["facility__name"]
    autocomplete_fields = ["facility", "insurer"]
