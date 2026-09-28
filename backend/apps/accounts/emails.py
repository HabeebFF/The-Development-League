"""Emails sent by the accounts app. Links point at the website (FRONTEND_URL)."""

from django.conf import settings
from django.core.mail import send_mail

from .models import Invite, User


def send_invite(invite: Invite) -> None:
    link = f"{settings.FRONTEND_URL}/invite/{invite.token}"
    role = invite.get_role_display().lower()
    send_mail(
        subject=f"You're invited to join {invite.team.name} on The Development League",
        message=(
            f"You've been invited to join {invite.team.name} as a {role}.\n\n"
            f"Accept the invite here: {link}\n\n"
            f"The link expires on {invite.expires_at:%d %b %Y}."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invite.email],
    )


def send_password_reset(user: User, uid: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/auth/reset?uid={uid}&token={token}"
    send_mail(
        subject="Reset your password - The Development League",
        message=(
            "Someone asked to reset the password for this account.\n\n"
            f"Choose a new password here: {link}\n\n"
            "If it wasn't you, ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
