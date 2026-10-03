import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils import timezone

# Plan features everyone gets while the site is public (``PUBLIC_SITE``).
PUBLIC_FEATURES = {"rotations.view"}


class EmailUserManager(UserManager):
    def _create_user(self, username, email, password, **extra_fields):
        email = (email or "").strip().lower()
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

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    @property
    def is_super_admin(self) -> bool:
        return self.is_superuser

    @property
    def is_league_staff(self) -> bool:
        """Staff/Analyst role, the Super Admin, or Django's staff flag."""
        if self.is_superuser or self.is_staff:
            return True
        return StaffProfile.objects.filter(user=self).exists()

    def active_memberships(self):
        return self.memberships.filter(is_active=True).select_related("team", "team__plan")

    def features(self) -> set[str]:
        """Feature codes this user can use (staff can use everything)."""
        if self.is_league_staff:
            return set(Feature.objects.values_list("code", flat=True))
        codes = set(
            Feature.objects.filter(
                plans__teams__memberships__user=self, plans__teams__memberships__is_active=True
            ).values_list("code", flat=True)
        )
        # While the site is public, replays and rotations are open to every account too.
        return codes | PUBLIC_FEATURES if settings.PUBLIC_SITE else codes

    def has_feature(self, code: str) -> bool:
        return code in self.features()

    def manages(self, team) -> bool:
        return self.memberships.filter(
            team=team, role=Membership.Role.MANAGER, is_active=True
        ).exists()


class StaffProfile(models.Model):
    """League staff and analysts: they upload matches and plot rotations.

    The Super Admin is a Django superuser and needs no profile.
    """

    class Role(models.TextChoices):
        STAFF = "STAFF", "League staff"
        ANALYST = "ANALYST", "Analyst"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff_profile")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user} ({self.role})"


class Feature(models.Model):
    """A gated capability, e.g. ``rotations.view``. Pages check features, never plans."""

    code = models.CharField(max_length=60, unique=True)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class Plan(models.Model):
    """What a team account can see. League teams get ``league_team`` (everything)."""

    LEAGUE_TEAM = "league_team"

    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    features = models.ManyToManyField(Feature, blank=True, related_name="plans")

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        MANAGER = "MANAGER", "Team manager"
        PLAYER = "PLAYER", "Team player"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    team = models.ForeignKey("league.Team", on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.PLAYER)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["team", "role", "user__email"]
        constraints = [
            models.UniqueConstraint(fields=["user", "team"], name="unique_membership"),
        ]

    def __str__(self) -> str:
        return f"{self.user} in {self.team} ({self.role})"


def invite_token() -> str:
    return secrets.token_urlsafe(32)


def invite_expiry():
    return timezone.now() + timedelta(days=INVITE_DAYS)


INVITE_DAYS = 7


class Invite(models.Model):
    team = models.ForeignKey("league.Team", on_delete=models.CASCADE, related_name="invites")
    email = models.EmailField()
    role = models.CharField(
        max_length=10, choices=Membership.Role.choices, default=Membership.Role.PLAYER
    )
    token = models.CharField(max_length=64, unique=True, default=invite_token)
    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="invites_sent"
    )
    expires_at = models.DateTimeField(default=invite_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Invite {self.email} to {self.team}"

    @property
    def is_open(self) -> bool:
        return (
            self.accepted_at is None
            and self.revoked_at is None
            and self.expires_at > timezone.now()
        )


class PlayerClaim(models.Model):
    """A user asking to be linked to a game UID; staff approve it."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="player_claims")
    game_uid = models.BigIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="PENDING"),
                name="one_pending_claim_per_user",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} claims {self.game_uid} ({self.status})"
