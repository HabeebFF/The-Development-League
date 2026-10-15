"""Visitor analytics: page views, how long people stay, and what they do on each page.

Visitors without an account are told apart by an anonymous code made from their IP, browser
and a secret that changes every day, so nobody can be followed from one day to the next and
no IP is stored. Signed-in people's views are linked to their account (see /privacy).
"""

import uuid

from django.conf import settings
from django.db import models


class PageView(models.Model):
    class Audience(models.TextChoices):
        GUEST = "guest", "Guest"
        MEMBER = "member", "Team member"
        STAFF = "staff", "Staff"

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # Given to the browser so it can report time on page and actions for this view.
    key = models.UUIDField(default=uuid.uuid4, unique=True, null=True, editable=False)
    path = models.CharField(max_length=200)
    visitor = models.CharField(max_length=16, help_text="Anonymous code, new every day")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="page_views",
    )
    source = models.CharField(max_length=60, blank=True, help_text="Where they came from")
    device = models.CharField(max_length=10)
    browser = models.CharField(max_length=20)
    os = models.CharField(max_length=20)
    audience = models.CharField(max_length=6, choices=Audience.choices, default=Audience.GUEST)
    duration_s = models.PositiveIntegerField(null=True, blank=True, help_text="Time on page")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["audience", "created_at"])]

    def __str__(self) -> str:
        return f"{self.path} at {self.created_at:%Y-%m-%d %H:%M}"


class Action(models.Model):
    """Something done on a page: a button pressed, an option picked, a save, a sign-in."""

    view = models.ForeignKey(PageView, on_delete=models.CASCADE, related_name="actions")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    name = models.CharField(max_length=80, help_text='e.g. "Pressed Play", "Signed in"')
    detail = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.name} on {self.view.path}"
