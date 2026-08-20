from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import Provider, ProviderFacility, Specialty


class ProviderFacilityInline(admin.TabularInline):
    model = ProviderFacility
    extra = 0
    autocomplete_fields = ["facility"]
    filter_horizontal = ["service_types"]


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = [
        "name_en",
        "code",
        "routable",
        "is_triage_target",
        "provider_count",
        "sort_order",
    ]
    search_fields = ["code", "name_en", "name_rw", "name_fr"]
    list_filter = ["is_triage_target"]
    filter_horizontal = ["service_types"]
    prepopulated_fields = {"code": ("name_en",)}

    @admin.display(boolean=True, description="Reaches facilities")
    def routable(self, obj):
        """A specialty with no mapped services cannot be recommended: the
        facility search has nothing to filter on."""
        return obj.service_types.exists()

    @admin.display(description="Doctors")
    def provider_count(self, obj):
        return obj.providers.count()


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = [
        "display_name",
        "specialty_list",
        "facility_list",
        "verification_badge",
        "active",
    ]
    list_filter = ["active", "specialties", "placements__facility__district"]
    search_fields = ["full_name", "slug"]
    prepopulated_fields = {"slug": ("full_name",)}
    filter_horizontal = ["specialties"]
    inlines = [ProviderFacilityInline]
    actions = ["mark_verified"]
    readonly_fields = ["created_at", "updated_at", "verified_at"]

    fieldsets = (
        (None, {"fields": ("title", "full_name", "slug", "active")}),
        ("Clinical", {"fields": ("specialties", "languages")}),
        (
            "Profile",
            {
                "fields": ("photo_url", "bio_en"),
                "description": (
                    "Never enter qualifications or claims that have not been "
                    "confirmed with the facility. A doctor profile is a public "
                    "statement about a named person."
                ),
            },
        ),
        ("Verification", {"fields": ("verified_at",)}),
        ("Audit", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("specialties", "placements__facility")
        )

    @admin.display(description="Specialties")
    def specialty_list(self, obj):
        names = [s.name_en for s in obj.specialties.all()]
        return ", ".join(names) if names else "-"

    @admin.display(description="Practises at")
    def facility_list(self, obj):
        names = [p.facility.name for p in obj.placements.all() if p.active]
        return ", ".join(names) if names else format_html(
            '<span style="color:#b45309">no active placement</span>'
        )

    @admin.display(description="Verified", ordering="verified_at")
    def verification_badge(self, obj):
        if obj.is_verified:
            return format_html(
                '<span style="color:#0B6B55;font-weight:600">Verified {}</span>',
                obj.verified_at.date(),
            )
        return format_html('<span style="color:#94620A;font-weight:600">Pending</span>')

    @admin.action(description="Mark selected doctors as VERIFIED")
    def mark_verified(self, request, queryset):
        updated = queryset.update(verified_at=timezone.now())
        self.message_user(request, f"{updated} doctor(s) marked verified.")
