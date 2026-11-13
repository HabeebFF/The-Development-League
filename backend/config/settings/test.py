from .base import *  # noqa: F403
from .base import BASE_DIR

SECRET_KEY = "test-only-not-secret-but-long-enough-for-hs256"
DEBUG = False
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
USE_S3 = False
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
MEDIA_ROOT = BASE_DIR / "test-media"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

AUTH_COOKIE_SECURE = False
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
SIMPLE_JWT = {**SIMPLE_JWT, "SIGNING_KEY": SECRET_KEY}  # noqa: F405

# The daily bonus would change every balance the older tests check; its own tests switch it on.
PREDICTIONS_DAILY_BONUS = 0
