from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import SECRET_KEY, env_bool

if len(SECRET_KEY or "") < 50:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set (50+ characters) in production")

DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_CONTENT_TYPE_NOSNIFF = True
