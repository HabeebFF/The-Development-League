from .base import *  # noqa: F403
from .base import BASE_DIR

SECRET_KEY = "test-only-not-secret"
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
