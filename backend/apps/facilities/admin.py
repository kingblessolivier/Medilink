"""Django admin as the facility verification tool.

This is the whole reason for choosing Django over FastAPI: the ops workflow
described in docs/01 section 1 costs zero lines of custom UI.
"""

from django.contrib import admin, messages
from django.contrib.gis.admin import GISModelAdmin
from django.utils import timezone
from django.utils.html import format_html

from apps.insurance.models import FacilityInsurer

from .models import Facility, FacilityService, OpeningHours, ServiceType


class OpeningHoursInline(admin.TabularInline):
    model = OpeningHours
    extra = 0
    ordering = ["weekday", "opens_at"]


class FacilityServiceInline(admin.TabularInline):
    model = FacilityService
    extra = 0
    autocomplete_fields = ["service_type"]


class FacilityInsurerInline(admin.TabularInline):
    model = FacilityInsurer
    extra = 0
    autocomplete_fields = ["insurer"]


@admin.register(Facility)
class FacilityAdmin(GISModelAdmin):
    list_display = [
        "name",
        "district",
        "level",
        "verification_badge",
        "insurer_list",
        "reports_queue",
    ]
    list_filter = [
        "district",
        "level",
        "ownership",
        "reports_queue",
        ("verified_at", admin.EmptyFieldListFilter),
    ]
    search_fields = ["name", "district", "sector", "address"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [OpeningHoursInline, FacilityServiceInline, FacilityInsurerInline]
    actions = ["mark_verified", "mark_unverified"]
    readonly_fields = ["created_at", "updated_at", "verified_at", "verified_by"]

    fieldsets = (
        (None, {"fields": ("name", "slug", "level", "ownership")}),
        (
            "Location",
            {
                "fields": ("province", "district", "sector", "address", "location"),
                "description": (
                    "Coordinates must be captured on site. A plausible-looking "
                    "guessed coordinate produces a directory that ranks "
                    "facilities wrongly and hides bugs in the geo query."
                ),
            },
        ),
        ("Contact", {"fields": ("phone", "email")}),
        (
            "Verification",
            {
                "fields": (
                    "verified_at",
                    "verified_by",
                    "verification_note",
                    "reports_queue",
                )
            },
        ),
        ("Audit", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Verified", ordering="verified_at")
    def verification_badge(self, obj):
        if obj.is_verified:
            return format_html(
                '<span style="color:#15803d;font-weight:600">Verified {}</span>',
                obj.verified_at.date(),
            )
        return format_html(
            '<span style="color:#b45309;font-weight:600">Not verified</span>'
        )

    @admin.display(description="Insurers")
    def insurer_list(self, obj):
        codes = [fi.insurer.code for fi in obj.insurers.all()]
        return ", ".join(codes) if codes else "-"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("insurers__insurer")

    @admin.action(description="Mark selected facilities as VERIFIED")
    def mark_verified(self, request, queryset):
        missing_hours = queryset.filter(opening_hours__isnull=True).distinct()
        if missing_hours.exists():
            self.message_user(
                request,
                (
                    f"{missing_hours.count()} facility(ies) have no opening hours "
                    "and were skipped. A verified facility with no hours always "
                    "reads as closed."
                ),
                level=messages.WARNING,
            )
        ready = queryset.exclude(pk__in=missing_hours.values("pk"))
        updated = ready.update(verified_at=timezone.now(), verified_by=request.user)
        self.message_user(request, f"{updated} facility(ies) marked verified.")

    @admin.action(description="Mark selected facilities as NOT verified")
    def mark_unverified(self, request, queryset):
        updated = queryset.update(verified_at=None, verified_by=None)
        self.message_user(
            request,
            f"{updated} facility(ies) hidden from patient search.",
            level=messages.WARNING,
        )


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ["name_en", "name_rw", "name_fr", "code", "sort_order"]
    search_fields = ["code", "name_en", "name_rw", "name_fr"]
    prepopulated_fields = {"code": ("name_en",)}
