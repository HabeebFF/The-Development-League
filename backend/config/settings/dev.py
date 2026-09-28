from .base import *  # noqa: F403
from .base import env

DEBUG = True
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-not-secret-but-long-enough-for-hs256")

AUTH_COOKIE_SECURE = False
SIMPLE_JWT = {**SIMPLE_JWT, "SIGNING_KEY": SECRET_KEY}  # noqa: F405
