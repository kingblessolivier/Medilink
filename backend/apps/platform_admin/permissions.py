"""Who may see the whole platform.

Facility staff are scoped to one facility by apps/staff/permissions.py. These
endpoints are the opposite: they cross every facility, every provider and every
patient count in the country. So the bar is a superuser, not `is_staff`.

`is_staff` only means "may open Django admin", and it is routinely granted to
people who need to edit one lookup table. Reading platform-wide figures and
approving a facility into patient-facing search is a different privilege, and
conflating the two is how a lookup-table editor ends up verifying hospitals.
"""

from rest_framework.permissions import BasePermission


class IsPlatformAdmin(BasePermission):
    message = "This endpoint is restricted to MediLink platform administrators."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_superuser
        )
