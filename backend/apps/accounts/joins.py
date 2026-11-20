"""Players asking to join their team: they ask from My account, the team's manager (or
league staff, when the team has no manager) accepts or rejects. Only accounts linked to a
game UID can ask, so managers can see who is asking and whether they played for the team.

Someone can also ask to join as the team's manager (``role=MANAGER``, no UID needed). Only
league staff accept those; the team's current manager can see them but not answer."""

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.league.models import Player, Team
from common.permissions import IsStaff, IsTeamManagerOrStaff

from .models import JoinRequest, Membership


def matches_for(player: Player | None, team: Team) -> int:
    from apps.results.models import PlayerMatchResult

    if player is None:
        return 0
    return PlayerMatchResult.objects.filter(player=player, team=team).count()


def _team(team: Team | None, player: Player | None = None) -> dict | None:
    if team is None:
        return None
    row = {"id": team.pk, "name": team.name, "tag": team.tag, "slug": team.slug}
    if player is not None:
        row["matches"] = matches_for(player, team)
    return row


def has_manager(team: Team) -> bool:
    return Membership.objects.filter(
        team=team, role=Membership.Role.MANAGER, is_active=True
    ).exists()


class JoinRequestSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.display_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    team = serializers.SerializerMethodField()
    player = serializers.SerializerMethodField()
    reviewed_by = serializers.StringRelatedField()

    class Meta:
        model = JoinRequest
        fields = [
            "id",
            "user_name",
            "email",
            "team",
            "player",
            "role",
            "note",
            "status",
            "voided_bets",
            "reviewed_by",
            "reviewed_at",
            "created_at",
        ]

    def get_team(self, r: JoinRequest) -> dict:
        return _team(r.team)

    def get_player(self, r: JoinRequest) -> dict | None:
        """The player the account is linked to, and how much they played for this team."""
        player = Player.objects.filter(user=r.user).select_related("current_team").first()
        if player is None:
            return None
        return {
            "name": player.display_name,
            "game_uid": str(player.game_uid),
            "matches_for_team": matches_for(player, r.team),
            "current_team": _team(player.current_team),
        }


class AskSerializer(serializers.Serializer):
    team = serializers.SlugRelatedField(
        slug_field="slug", queryset=Team.objects.filter(is_league_member=True)
    )
    note = serializers.CharField(max_length=200, required=False, allow_blank=True)
    role = serializers.ChoiceField(
        choices=Membership.Role.choices, required=False, default=Membership.Role.PLAYER
    )


class MyJoinRequestView(APIView):
    """GET: the teams I can ask to join (mine from the logs first) and my latest request.
    POST {team, note}: ask to join. DELETE: cancel my waiting request."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        player = Player.objects.filter(user=user).select_related("current_team").first()
        membership = user.active_memberships().first()
        latest = user.join_requests.select_related("team", "reviewed_by").first()
        teams = Team.objects.filter(is_league_member=True).order_by("name")
        return Response(
            {
                "player": {"name": player.display_name, "game_uid": str(player.game_uid)}
                if player
                else None,
                "on_team": {**_team(membership.team), "role": membership.role}
                if membership
                else None,
                "suggested": _team(player.current_team, player) if player else None,
                "teams": [_team(t) for t in teams],
                "request": JoinRequestSerializer(latest).data if latest else None,
            }
        )

    def post(self, request):
        user = request.user
        data = AskSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        team = data.validated_data["team"]
        role = data.validated_data["role"]
        as_manager = role == Membership.Role.MANAGER
        if not as_manager and not Player.objects.filter(user=user).exists():
            raise ValidationError(
                {"detail": "Link your Free Fire UID first, so your manager can see who you are."}
            )
        if user.is_league_staff:
            raise ValidationError({"detail": "League staff can't join a team this way."})
        on = user.active_memberships().first()
        if as_manager and on is not None and on.team_id == team.pk:
            if on.role == Membership.Role.MANAGER:
                raise ValidationError({"detail": f"You already manage {team.name}."})
            on = None  # a player on the team asking to become its manager
        if on is not None:
            msg = (
                f"You're already on {on.team.name}."
                if on.team_id == team.pk
                else f"You're on {on.team.name}. Ask its manager to remove you first."
            )
            raise ValidationError({"detail": msg})
        with transaction.atomic():
            user.join_requests.select_for_update().filter(status=JoinRequest.Status.PENDING).update(
                status=JoinRequest.Status.CANCELLED, reviewed_at=timezone.now()
            )
            made = JoinRequest.objects.create(
                user=user,
                team=team,
                role=role,
                note=(data.validated_data.get("note") or "").strip(),
            )
        return Response(JoinRequestSerializer(made).data, status=status.HTTP_201_CREATED)

    def delete(self, request):
        n = request.user.join_requests.filter(status=JoinRequest.Status.PENDING).update(
            status=JoinRequest.Status.CANCELLED, reviewed_at=timezone.now()
        )
        if not n:
            raise ValidationError({"detail": "You have no request waiting."})
        return Response(status=status.HTTP_204_NO_CONTENT)


def review(join: JoinRequest, reviewer, accept: bool) -> JoinRequest:
    """Accept (add them to the team as a player) or reject a waiting request."""
    from apps.predictions.markets import withdraw_blocked

    with transaction.atomic():
        join = JoinRequest.objects.select_for_update().get(pk=join.pk)
        if join.status != JoinRequest.Status.PENDING:
            raise ValidationError({"detail": "This request was already answered or cancelled."})
        if join.role == Membership.Role.MANAGER and not reviewer.is_league_staff:
            raise PermissionDenied("Only TDL staff can answer a request to manage a team.")
        if accept:
            on = join.user.active_memberships().exclude(team=join.team).first()
            if on is not None:
                raise ValidationError(
                    {"detail": f"{join.user} is already on {on.team.name}. Reject this one."}
                )
            membership, made = Membership.objects.get_or_create(
                user=join.user, team=join.team, defaults={"role": join.role}
            )
            if not made and (not membership.is_active or join.role == Membership.Role.MANAGER):
                # Back on the team (as asked), or a player on it becoming its manager.
                membership.is_active, membership.role = True, join.role
                membership.save(update_fields=["is_active", "role"])
            player = Player.objects.filter(user=join.user).first()
            why = f"Joined {join.team.name}: can't predict on your own team"
            join.voided_bets = len(withdraw_blocked(join.user, player, why))
        join.status = JoinRequest.Status.ACCEPTED if accept else JoinRequest.Status.REJECTED
        join.reviewed_by, join.reviewed_at = reviewer, timezone.now()
        join.save(update_fields=["status", "reviewed_by", "reviewed_at", "voided_bets"])
    return join


class TeamJoinRequestViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """A team's waiting join requests, for its managers and staff, to accept or reject."""

    permission_classes = [IsTeamManagerOrStaff]
    serializer_class = JoinRequestSerializer

    def get_team(self) -> Team:
        if not hasattr(self, "_team"):
            self._team = get_object_or_404(Team, slug=self.kwargs["slug"])
        return self._team

    def get_queryset(self):
        return JoinRequest.objects.filter(
            team=self.get_team(), status=JoinRequest.Status.PENDING
        ).select_related("user", "team")

    @action(detail=True, methods=["post"])
    def accept(self, request, slug=None, pk=None):
        return Response(JoinRequestSerializer(review(self.get_object(), request.user, True)).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, slug=None, pk=None):
        return Response(JoinRequestSerializer(review(self.get_object(), request.user, False)).data)


class StaffJoinRequestViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Staff: every waiting request, flagged when the team has no manager to answer it.
    ``?unmanaged=1`` lists only those."""

    permission_classes = [IsStaff]
    serializer_class = JoinRequestSerializer

    def get_queryset(self):
        qs = JoinRequest.objects.filter(status=JoinRequest.Status.PENDING).select_related(
            "user", "team"
        )
        if self.request.query_params.get("unmanaged"):
            # Staff answer requests for teams nobody manages, and every request to manage.
            managed = Membership.objects.filter(
                role=Membership.Role.MANAGER, is_active=True
            ).values("team_id")
            qs = qs.filter(~Q(team_id__in=managed) | Q(role=Membership.Role.MANAGER))
        return qs

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        rows = response.data["results"] if isinstance(response.data, dict) else response.data
        for row in rows:
            row["team_has_manager"] = has_manager(Team.objects.get(pk=row["team"]["id"]))
        return response
