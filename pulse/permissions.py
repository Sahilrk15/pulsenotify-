from rest_framework.permissions import BasePermission

from .models import UserProfile


class IsAdminUser(BasePermission):
    """Only users whose profile.role is ADMIN may pass. Others get 403."""

    message = 'Admin access required.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False  # DRF turns this into 401 because JWT auth defines a WWW-Authenticate header
        profile = getattr(user, 'profile', None)
        return profile is not None and profile.role == UserProfile.Role.ADMIN
