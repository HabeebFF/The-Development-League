"""Visitor analytics: one row per page view, counted by the site itself (no cookies).

Visitors are told apart by an anonymous code made from their IP, browser and a secret that
changes every day, so nobody can be followed from one day to the next and no IP is stored.
"""

from django.db import models


class PageView(models.Model):
    class Audience(models.TextChoices):
        GUEST = "guest", "Guest"
        MEMBER = "member", "Team member"
        STAFF = "staff", "Staff"

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    path = models.CharField(max_length=200)
    visitor = models.CharField(max_length=16, help_text="Anonymous code, new every day")
    source = models.CharField(max_length=60, blank=True, help_text="Where they came from")
    device = models.CharField(max_length=10)
    browser = models.CharField(max_length=20)
    os = models.CharField(max_length=20)
    audience = models.CharField(max_length=6, choices=Audience.choices, default=Audience.GUEST)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["audience", "created_at"])]

    def __str__(self) -> str:
        return f"{self.path} at {self.created_at:%Y-%m-%d %H:%M}"
