from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class EmailUserManager(UserManager):
    def _create_user(self, username, email, password, **extra_fields):
        email = self.normalize_email(email)
        if not email:
            raise ValueError("An email address is required")
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(None, email, password, **extra_fields)

    def create_superuser(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(None, email, password, **extra_fields)


class User(AbstractUser):
    """Signs in with email. Roles and team memberships arrive in step (c)."""

    username = None
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=80, blank=True)
    preferred_language = models.CharField(max_length=10, default="en")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = EmailUserManager()

    def __str__(self) -> str:
        return self.display_name or self.email
