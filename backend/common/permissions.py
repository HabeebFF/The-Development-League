"""Permission classes. Every API view names its permissions explicitly."""

from rest_framework.permissions import SAFE_METHODS, BasePermission


def _user(request):
    user = request.user
    return user if user and user.is_authenticated else None


class IsStaff(BasePermission):
    """League staff and analysts (and the Super Admin)."""

    message = "Only league staff can do this."

    def has_permission(self, request, view) -> bool:
        user = _user(request)
        return bool(user and user.is_league_staff)


class IsSuperAdmin(BasePermission):
    message = "Only the Super Admin can do this."

    def has_permission(self, request, view) -> bool:
        user = _user(request)
        return bool(user and user.is_superuser)


class ReadOnly(BasePermission):
    def has_permission(self, request, view) -> bool:
        return request.method in SAFE_METHODS


def HasFeature(code: str) -> type[BasePermission]:  # noqa: N802 - reads like a class
    """Allow users whose team plan includes ``code`` (staff always pass)."""

    class _HasFeature(BasePermission):
        message = "Your team's plan does not include this page."

        def has_permission(self, request, view) -> bool:
            user = _user(request)
            return bool(user and user.has_feature(code))

    _HasFeature.__name__ = f"HasFeature[{code}]"
    return _HasFeature


class IsTeamManagerOrStaff(BasePermission):
    """For views with ``get_team()``: that team's managers, or staff."""

    message = "Only this team's managers can do this."

    def has_permission(self, request, view) -> bool:
        user = _user(request)
        if not user:
            return False
        return user.is_league_staff or user.manages(view.get_team())


class IsTeamMemberOrStaff(BasePermission):
    """For views with ``get_team()``: anyone on that team, or staff."""

    message = "Only this team's members can see this."

    def has_permission(self, request, view) -> bool:
        user = _user(request)
        if not user:
            return False
        if user.is_league_staff:
            return True
        return user.memberships.filter(team=view.get_team(), is_active=True).exists()
