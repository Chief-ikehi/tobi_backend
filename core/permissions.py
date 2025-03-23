from rest_framework.permissions import BasePermission
from core.models import User
from rest_framework.permissions import SAFE_METHODS
from rest_framework.permissions import BasePermission
from .utils import has_active_membership

class IsAgentOrReadOnly(BasePermission):
    """
    Only agents can POST/PUT/DELETE. Everyone can read.
    """

    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True

        # Must be authenticated and role must be AGENT or ADMIN or SUPERUSER
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.AGENT
            or request.user.role == User.Role.ADMIN
            or request.user.is_staff
        )


class IsAgentOwnerOrAdmin(BasePermission):
    """
    Only the agent who owns the property or an admin/superuser can update/delete.
    Everyone can read.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        return (
            request.user.is_authenticated and (
                obj.agent == request.user or
                request.user.role == User.Role.ADMIN or
                request.user.is_staff
            )
        )

class HasActiveMembership(BasePermission):
    def has_permission(self, request, view):
        return has_active_membership(request.user)
