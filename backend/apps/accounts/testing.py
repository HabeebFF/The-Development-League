"""Test helpers shared across apps."""

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


def signed_in_client(email: str = "member@tdl.test") -> APIClient:
    """An API client signed in as an ordinary account (no team, not staff)."""
    user, _ = get_user_model().objects.get_or_create(email=email)
    client = APIClient()
    client.force_authenticate(user)
    return client
