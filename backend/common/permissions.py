from rest_framework.permissions import BasePermission


class IsStaff(BasePermission):
    """League staff and analysts.

    For now this is Django's ``is_staff`` flag; step (c) adds staff roles on top.
    """

    message = "Only league staff can do this."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))
