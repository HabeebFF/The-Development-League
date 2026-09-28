"""Sign-in via JWT stored in httpOnly cookies (JavaScript cannot read them).

Because the browser sends cookies automatically, unsafe requests also need the CSRF
token (cookie ``csrftoken`` echoed in the ``X-CSRFToken`` header), exactly like
Django's session auth.
"""

from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


def enforce_csrf(request) -> None:
    def dummy_get_response(_request):  # pragma: no cover - never called
        return None

    check = CSRFCheck(dummy_get_response)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        raw = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS)
        if not raw:
            return None
        try:
            token = self.get_validated_token(raw)
        except (InvalidToken, TokenError):
            return None  # expired: the client refreshes, anonymous until then
        user = self.get_user(token)
        enforce_csrf(request)
        return user, token

    def authenticate_header(self, request):
        return 'Bearer realm="api"'
