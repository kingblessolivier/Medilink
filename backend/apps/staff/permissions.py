"""Facility scoping - the single most important authorisation control here.

Never rely on each view remembering to filter by facility. One forgotten
.filter() exposes another clinic's patient list. Everything goes through these
two helpers, and apps/queueing/tests/test_scoping.py asserts it for every
staff endpoint.
"""

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


def active_staff(request):
    """Return the caller's StaffMember, or raise PermissionDenied."""
    staff = getattr(request.user, "staffmember", None)
    if staff is None or not staff.active:
        raise PermissionDenied("You are not registered as active facility staff.")
    return staff


class IsFacilityStaff(BasePermission):
    message = "You are not registered as active facility staff."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        staff = getattr(request.user, "staffmember", None)
        return staff is not None and staff.active


class IsQueueManager(IsFacilityStaff):
    """Receptionists and facility admins. Clinicians may read, not mutate."""

    message = "Your role cannot modify the queue."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.staffmember.can_manage_queue


class IsFacilityAdmin(IsFacilityStaff):
    """Facility administrators only.

    Stricter than IsQueueManager on purpose: a receptionist may move the queue
    all day and must not be able to create accounts or change roles. The
    dashboards spec says the same thing from the other side - "Receptionist
    sees FA-03 and FA-06 only".

    This guards the one staff surface that can grant access rather than use
    it, so it checks the role directly rather than reusing can_manage_queue,
    which deliberately includes receptionists.
    """

    message = "Only a facility administrator can manage staff accounts."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.staffmember.role == request.user.staffmember.Role.ADMIN


class FacilityScopedMixin:
    """Restrict a queryset to the caller's own facility."""

    def get_queryset(self):
        staff = active_staff(self.request)
        return super().get_queryset().filter(facility_id=staff.facility_id)
