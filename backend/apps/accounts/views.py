"""Sign-in, profile, invites, team members, game UID linking and staff management."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.league.models import Player, Team
from common.authentication import enforce_csrf
from common.permissions import IsStaff, IsSuperAdmin, IsTeamManagerOrStaff, IsTeamMemberOrStaff

from . import emails
from .models import Invite, Membership, PlayerClaim, StaffProfile, User
from .serializers import (
    InviteAcceptSerializer,
    InvitePublicSerializer,
    InviteSerializer,
    LinkUidSerializer,
    LoginSerializer,
    MemberSerializer,
    MeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetSerializer,
    PlayerClaimSerializer,
    StaffMemberSerializer,
    validate_new_password,
)

# -- cookies -----------------------------------------------------------------------------------


def _cookie_args(max_age: int, path: str = "/") -> dict:
    return {
        "max_age": max_age,
        "path": path,
        "domain": settings.AUTH_COOKIE_DOMAIN,
        "secure": settings.AUTH_COOKIE_SECURE,
        "httponly": True,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
    }


REFRESH_PATH = "/api/v1/auth/"


def set_auth_cookies(response: Response, refresh: RefreshToken) -> Response:
    jwt = settings.SIMPLE_JWT
    response.set_cookie(
        settings.AUTH_COOKIE_ACCESS,
        str(refresh.access_token),
        **_cookie_args(int(jwt["ACCESS_TOKEN_LIFETIME"].total_seconds())),
    )
    response.set_cookie(
        settings.AUTH_COOKIE_REFRESH,
        str(refresh),
        **_cookie_args(int(jwt["REFRESH_TOKEN_LIFETIME"].total_seconds()), REFRESH_PATH),
    )
    return response


def clear_auth_cookies(response: Response) -> Response:
    domain = settings.AUTH_COOKIE_DOMAIN
    response.delete_cookie(settings.AUTH_COOKIE_ACCESS, path="/", domain=domain)
    response.delete_cookie(settings.AUTH_COOKIE_REFRESH, path=REFRESH_PATH, domain=domain)
    return response


def signed_in(user: User, request, code: int = status.HTTP_200_OK) -> Response:
    response = Response(MeSerializer(user, context={"request": request}).data, status=code)
    return set_auth_cookies(response, RefreshToken.for_user(user))


# -- auth ----------------------------------------------------------------------------------------


class SiteView(APIView):
    """What the website needs before anyone signs in: is it open to visitors?"""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request):
        return Response({"public": settings.PUBLIC_SITE})


@method_decorator(ensure_csrf_cookie, name="get")
class CsrfView(APIView):
    """Sets the ``csrftoken`` cookie; the site calls this once before signing in."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        enforce_csrf(request)
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = authenticate(
            request,
            email=data.validated_data["email"].strip().lower(),
            password=data.validated_data["password"],
        )
        if user is None:
            return Response(
                {"detail": "Wrong email or password."}, status=status.HTTP_400_BAD_REQUEST
            )
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
        return signed_in(user, request)


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        enforce_csrf(request)
        raw = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if not raw:
            return clear_auth_cookies(Response({"detail": "Not signed in."}, status=401))
        try:
            old = RefreshToken(raw)
            user = User.objects.get(pk=old["user_id"], is_active=True)
            old.blacklist()
        except (TokenError, User.DoesNotExist, KeyError):
            return clear_auth_cookies(Response({"detail": "Session expired."}, status=401))
        return set_auth_cookies(Response(status=204), RefreshToken.for_user(user))


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        enforce_csrf(request)
        raw = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except TokenError:
                pass
        return clear_auth_cookies(Response(status=204))


class PasswordResetView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        enforce_csrf(request)
        data = PasswordResetSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=data.validated_data["email"].strip(), is_active=True
        ).first()
        if user is not None and user.has_usable_password():
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            emails.send_password_reset(user, uid, default_token_generator.make_token(user))
        # Same answer either way, so the endpoint can't be used to find accounts.
        return Response(status=204)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        enforce_csrf(request)
        data = PasswordResetConfirmSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            pk = force_str(urlsafe_base64_decode(data.validated_data["uid"]))
            user = User.objects.get(pk=pk, is_active=True)
        except (ValueError, TypeError, OverflowError, User.DoesNotExist):
            user = None
        if user is None or not default_token_generator.check_token(
            user, data.validated_data["token"]
        ):
            return Response({"detail": "This reset link is invalid or has expired."}, status=400)
        validate_new_password(data.validated_data["new_password"], user)
        user.set_password(data.validated_data["new_password"])
        user.save(update_fields=["password"])
        blacklist_all_tokens(user)
        return Response(status=204)


def blacklist_all_tokens(user: User) -> None:
    """Sign the user out everywhere (after a password change)."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


# -- me ------------------------------------------------------------------------------------------


class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MeSerializer
    http_method_names = ["get", "patch"]

    def get_object(self):
        return self.request.user


class LinkUidView(APIView):
    """Ask to link this account to a game UID. Staff approve it."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = LinkUidSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            PlayerClaim.objects.filter(user=request.user, status=PlayerClaim.Status.PENDING).update(
                status=PlayerClaim.Status.REJECTED, reviewed_at=timezone.now()
            )
            claim = PlayerClaim.objects.create(
                user=request.user, game_uid=data.validated_data["game_uid"]
            )
        return Response(PlayerClaimSerializer(claim).data, status=status.HTTP_201_CREATED)


# -- invites and members ---------------------------------------------------------------------------


class TeamScopedMixin:
    def get_team(self) -> Team:
        if not hasattr(self, "_team"):
            self._team = get_object_or_404(Team, slug=self.kwargs["slug"])
        return self._team


class TeamInviteViewSet(
    TeamScopedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """A team's invites. DELETE revokes an open invite."""

    permission_classes = [IsTeamManagerOrStaff]
    serializer_class = InviteSerializer

    def get_queryset(self):
        return Invite.objects.filter(team=self.get_team()).select_related("invited_by")

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "team": self.get_team()}

    def perform_create(self, serializer):
        team = self.get_team()
        Invite.objects.filter(
            team=team, email__iexact=serializer.validated_data["email"], accepted_at__isnull=True
        ).update(revoked_at=timezone.now())
        invite = serializer.save(team=team, invited_by=self.request.user)
        transaction.on_commit(lambda: emails.send_invite(invite))

    def perform_destroy(self, invite: Invite):
        if invite.accepted_at is not None:
            raise ValidationError("This invite was already accepted.")
        invite.revoked_at = timezone.now()
        invite.save(update_fields=["revoked_at"])


class InviteView(APIView):
    """GET: what the invite is for. POST: accept it (signing up if needed)."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "invite_accept"

    def get_invite(self, token: str) -> Invite:
        return get_object_or_404(Invite.objects.select_related("team"), token=token)

    def get(self, request, token: str):
        return Response(InvitePublicSerializer(self.get_invite(token)).data)

    def post(self, request, token: str):
        invite = self.get_invite(token)
        if not invite.is_open:
            return Response({"detail": "This invite has expired or was withdrawn."}, status=400)

        created = False
        if request.user.is_authenticated:
            user = request.user
            if user.email.lower() != invite.email.lower():
                return Response(
                    {"detail": f"This invite is for {invite.email}. Sign in with that email."},
                    status=403,
                )
        else:
            enforce_csrf(request)
            if User.objects.filter(email__iexact=invite.email).exists():
                return Response(
                    {"detail": "An account with this email exists. Sign in, then accept."},
                    status=400,
                )
            data = InviteAcceptSerializer(data=request.data)
            data.is_valid(raise_exception=True)
            password = data.validated_data.get("password")
            if not password:
                raise ValidationError({"password": ["Choose a password."]})
            validate_new_password(password, User(email=invite.email))
            created = True

        with transaction.atomic():
            invite = Invite.objects.select_for_update().get(pk=invite.pk)
            if not invite.is_open:
                return Response({"detail": "This invite was already used."}, status=400)
            if created:
                user = User.objects.create_user(
                    email=invite.email.lower(),
                    password=password,
                    display_name=data.validated_data.get("display_name", ""),
                )
            membership, _ = Membership.objects.get_or_create(
                user=user, team=invite.team, defaults={"role": invite.role}
            )
            if not membership.is_active or membership.role != invite.role:
                membership.is_active = True
                membership.role = invite.role
                membership.save(update_fields=["is_active", "role"])
            invite.accepted_at = timezone.now()
            invite.save(update_fields=["accepted_at"])

        if created:
            return signed_in(user, request, status.HTTP_201_CREATED)
        return Response(MeSerializer(user, context={"request": request}).data)


class TeamMemberViewSet(
    TeamScopedMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Everyone on the team can list members; managers and staff change them.

    DELETE deactivates the membership (history is kept).
    """

    permission_classes = [IsTeamManagerOrStaff]
    serializer_class = MemberSerializer
    http_method_names = ["get", "patch", "delete"]

    def get_permissions(self):
        if self.action == "list":
            return [IsTeamMemberOrStaff()]
        return [IsTeamManagerOrStaff()]

    def get_queryset(self):
        return Membership.objects.filter(team=self.get_team()).select_related(
            "user", "user__player"
        )

    def _check_not_last_manager(self, membership: Membership, new_role=None, active=True):
        losing = membership.role == Membership.Role.MANAGER and (
            not active or (new_role and new_role != Membership.Role.MANAGER)
        )
        if not losing or self.request.user.is_league_staff:
            return
        others = Membership.objects.filter(
            team=membership.team, role=Membership.Role.MANAGER, is_active=True
        ).exclude(pk=membership.pk)
        if not others.exists():
            raise ValidationError("A team needs at least one manager.")

    def perform_update(self, serializer):
        self._check_not_last_manager(
            serializer.instance,
            serializer.validated_data.get("role"),
            serializer.validated_data.get("is_active", True),
        )
        serializer.save()

    def perform_destroy(self, membership: Membership):
        self._check_not_last_manager(membership, active=False)
        membership.is_active = False
        membership.save(update_fields=["is_active"])


# -- staff: UID claims and the staff list ---------------------------------------------


class PlayerClaimViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsStaff]
    serializer_class = PlayerClaimSerializer

    def get_queryset(self):
        qs = PlayerClaim.objects.select_related("user", "reviewed_by")
        wanted = self.request.query_params.get("status")
        return qs.filter(status=wanted) if wanted else qs

    def _review(self, claim: PlayerClaim, approved: bool) -> Response:
        if claim.status != PlayerClaim.Status.PENDING:
            raise ValidationError("This claim was already reviewed.")
        with transaction.atomic():
            if approved:
                player = Player.objects.select_for_update().filter(game_uid=claim.game_uid).first()
                if player and player.user_id and player.user_id != claim.user_id:
                    raise ValidationError("This UID is already linked to another account.")
                Player.objects.filter(user=claim.user).exclude(game_uid=claim.game_uid).update(
                    user=None
                )
                if player is None:
                    name = claim.user.display_name or claim.user.email.split("@")[0]
                    player = Player(
                        game_uid=claim.game_uid,
                        current_name_raw=name,
                        display_name=name,
                        search_name=name.casefold(),
                    )
                player.user = claim.user
                player.save()
            claim.status = PlayerClaim.Status.APPROVED if approved else PlayerClaim.Status.REJECTED
            claim.reviewed_by = self.request.user
            claim.reviewed_at = timezone.now()
            claim.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        return Response(PlayerClaimSerializer(claim).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._review(self.get_object(), approved=True)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._review(self.get_object(), approved=False)


class StaffViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Super Admin only: who is league staff or analyst."""

    permission_classes = [IsSuperAdmin]
    serializer_class = StaffMemberSerializer
    queryset = StaffProfile.objects.select_related("user").order_by("user__email")
    http_method_names = ["get", "post", "patch", "delete"]
