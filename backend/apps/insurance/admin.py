from django.contrib import admin
from django.utils.html import format_html

from .models import FacilityInsurer, FacilityServiceInsurer, Insurer


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


@admin.register(FacilityServiceInsurer)
class FacilityServiceInsurerAdmin(admin.ModelAdmin):
    list_display = [
        "facility_service",
        "insurer",
        "stated_coverage",
        "published_as",
        "confirmed_at",
    ]
    list_filter = ["coverage", "insurer", "facility_service__facility__district"]
    search_fields = ["facility_service__facility__name", "note"]
    autocomplete_fields = ["insurer"]

    @admin.display(description="Entered")
    def stated_coverage(self, obj):
        return obj.get_coverage_display()

    @admin.display(description="Shown to patients")
    def published_as(self, obj):
        """An unconfirmed row publishes as "Not confirmed" whatever was
        entered, so a half-finished record cannot make a coverage claim."""
        if obj.confirmed_at is None:
            return format_html(
                '<span style="color:#94620A;font-weight:600">Not confirmed</span>'
            )
        return format_html(
            '<span style="color:#0B6B55;font-weight:600">{}</span>',
            obj.get_coverage_display(),
        )
