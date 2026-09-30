from django.conf import settings
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models.functions import Lower
from rest_framework import serializers

from apps.league.models import Player, Team

from .models import Invite, Membership, PlayerClaim, StaffProfile, User


class TeamRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "name", "tag", "slug"]


class MembershipSerializer(serializers.ModelSerializer):
    team = TeamRefSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "team", "role", "is_active", "created_at"]


class MeSerializer(serializers.ModelSerializer):
    is_super_admin = serializers.BooleanField(read_only=True)
    staff_role = serializers.SerializerMethodField()
    memberships = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()
    player = serializers.SerializerMethodField()
    pending_uid_claim = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "display_name",
            "preferred_language",
            "is_super_admin",
            "staff_role",
            "memberships",
            "features",
            "player",
            "pending_uid_claim",
        ]
        read_only_fields = ["id", "email"]

    def get_staff_role(self, user: User) -> str | None:
        if user.is_superuser:
            return "SUPER_ADMIN"
        profile = StaffProfile.objects.filter(user=user).first()
        if profile:
            return profile.role
        return "STAFF" if user.is_staff else None

    def get_memberships(self, user: User):
        return MembershipSerializer(user.active_memberships(), many=True).data

    def get_features(self, user: User) -> list[str]:
        return sorted(user.features())

    def get_player(self, user: User):
        player = Player.objects.filter(user=user).first()
        if not player:
            return None
        return {"game_uid": str(player.game_uid), "display_name": player.display_name}

    def get_pending_uid_claim(self, user: User) -> str | None:
        claim = user.player_claims.filter(status=PlayerClaim.Status.PENDING).first()
        return str(claim.game_uid) if claim else None

    def validate_preferred_language(self, value: str) -> str:
        if value not in dict(settings.LANGUAGES):
            raise serializers.ValidationError("Unsupported language.")
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(trim_whitespace=False)


class InviteSerializer(serializers.ModelSerializer):
    invited_by = serializers.StringRelatedField()
    is_open = serializers.BooleanField(read_only=True)
    link = serializers.SerializerMethodField()

    class Meta:
        model = Invite
        fields = [
            "id",
            "email",
            "role",
            "link",
            "invited_by",
            "expires_at",
            "accepted_at",
            "revoked_at",
            "is_open",
            "created_at",
        ]
        read_only_fields = ["expires_at", "accepted_at", "revoked_at", "created_at"]

    def get_link(self, invite: Invite) -> str | None:
        """The accept link, so a manager can also send it by hand (e.g. on WhatsApp)."""
        return f"{settings.FRONTEND_URL}/invite/{invite.token}" if invite.is_open else None

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        team = self.context["team"]
        if Membership.objects.filter(team=team, user__email__iexact=value, is_active=True).exists():
            raise serializers.ValidationError("Already a member of this team.")
        return value

    def validate_role(self, value: str) -> str:
        user = self.context["request"].user
        if value == Membership.Role.MANAGER and not user.is_league_staff:
            raise serializers.ValidationError("Only league staff can invite managers.")
        return value


class InvitePublicSerializer(serializers.ModelSerializer):
    """What someone holding the invite link sees."""

    team = TeamRefSerializer(read_only=True)
    is_open = serializers.BooleanField(read_only=True)
    account_exists = serializers.SerializerMethodField()

    class Meta:
        model = Invite
        fields = ["team", "email", "role", "expires_at", "is_open", "account_exists"]

    def get_account_exists(self, invite: Invite) -> bool:
        return User.objects.filter(email__iexact=invite.email).exists()


class InviteAcceptSerializer(serializers.Serializer):
    """Only needed when the invitee has no account yet."""

    password = serializers.CharField(required=False, trim_whitespace=False)
    display_name = serializers.CharField(required=False, max_length=80, allow_blank=True)


class MemberSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    display_name = serializers.CharField(source="user.display_name", read_only=True)
    game_uid = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = ["id", "email", "display_name", "game_uid", "role", "is_active", "created_at"]
        read_only_fields = ["created_at"]

    def get_game_uid(self, membership: Membership) -> str | None:
        player = getattr(membership.user, "player", None)
        return str(player.game_uid) if player else None

    def validate_role(self, value: str) -> str:
        user = self.context["request"].user
        if value == Membership.Role.MANAGER and not user.is_league_staff:
            raise serializers.ValidationError("Only league staff can make someone a manager.")
        return value


class LinkUidSerializer(serializers.Serializer):
    game_uid = serializers.CharField(max_length=20)

    def validate_game_uid(self, value: str) -> int:
        value = value.strip()
        if not value.isdigit():
            raise serializers.ValidationError("A game UID is digits only.")
        uid = int(value)
        user = self.context["request"].user
        taken = Player.objects.filter(game_uid=uid, user__isnull=False).exclude(user=user)
        if taken.exists():
            raise serializers.ValidationError("This UID is already linked to another account.")
        return uid


class PlayerClaimSerializer(serializers.ModelSerializer):
    user = serializers.EmailField(source="user.email", read_only=True)
    game_uid = serializers.CharField(read_only=True)
    player_name = serializers.SerializerMethodField()
    reviewed_by = serializers.StringRelatedField()

    class Meta:
        model = PlayerClaim
        fields = [
            "id",
            "user",
            "game_uid",
            "player_name",
            "status",
            "reviewed_by",
            "reviewed_at",
            "created_at",
        ]

    def get_player_name(self, claim: PlayerClaim) -> str | None:
        player = Player.objects.filter(game_uid=claim.game_uid).first()
        return player.display_name if player else None


class StaffMemberSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    user = serializers.SerializerMethodField()

    class Meta:
        model = StaffProfile
        fields = ["id", "email", "user", "role", "created_at"]
        read_only_fields = ["created_at"]

    def get_user(self, profile: StaffProfile) -> dict:
        return {"id": profile.user_id, "email": profile.user.email}

    def validate_email(self, value: str) -> User:
        user = User.objects.annotate(e=Lower("email")).filter(e=value.strip().lower()).first()
        if user is None:
            raise serializers.ValidationError("No account with this email.")
        if StaffProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError("Already on the staff.")
        return user

    def update(self, instance, validated_data):
        validated_data.pop("email", None)  # a staff entry can't be moved to another user
        return super().update(instance, validated_data)

    def create(self, validated_data):
        return StaffProfile.objects.create(
            user=validated_data["email"], role=validated_data.get("role", StaffProfile.Role.STAFF)
        )


def validate_new_password(password: str, user: User | None = None) -> None:
    try:
        password_validation.validate_password(password, user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"password": list(exc.messages)}) from exc
