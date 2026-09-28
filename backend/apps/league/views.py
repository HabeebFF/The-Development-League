"""Teams, players, aliases and rosters. Public reads; staff manage."""

from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from common.permissions import IsStaff

from .models import Player, RosterEntry, Team, TeamAlias
from .serializers import (
    PlayerAdminSerializer,
    RosterEntrySerializer,
    TeamAdminSerializer,
    TeamAliasSerializer,
    TeamDetailSerializer,
    TeamPublicSerializer,
)


class PublicTeamViewSet(viewsets.ReadOnlyModelViewSet):
    """League teams, visible to everyone. ``?search=`` matches name or tag."""

    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        qs = Team.objects.filter(is_league_member=True)
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(tag__icontains=search))
        return qs

    def get_serializer_class(self):
        return TeamDetailSerializer if self.action == "retrieve" else TeamPublicSerializer


class TeamAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaff]
    serializer_class = TeamAdminSerializer
    lookup_field = "slug"

    def get_queryset(self):
        qs = Team.objects.prefetch_related("aliases")
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(tag__icontains=search)
                | Q(aliases__in_game_name__icontains=search)
            ).distinct()
        return qs


class TeamAliasViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaff]
    serializer_class = TeamAliasSerializer

    def get_queryset(self):
        qs = TeamAlias.objects.select_related("team", "season")
        team = self.request.query_params.get("team")
        return qs.filter(team__slug=team) if team else qs


class PlayerAdminViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Players are created from match results; staff can correct names and teams."""

    permission_classes = [IsStaff]
    serializer_class = PlayerAdminSerializer
    http_method_names = ["get", "patch"]

    def get_queryset(self):
        qs = Player.objects.select_related("current_team", "user")
        search = self.request.query_params.get("search", "").strip()
        if search.isdigit():
            qs = qs.filter(game_uid=int(search))
        elif search:
            qs = qs.filter(search_name__icontains=search.casefold())
        team = self.request.query_params.get("team")
        return qs.filter(current_team__slug=team) if team else qs


class RosterEntryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaff]
    serializer_class = RosterEntrySerializer

    def get_queryset(self):
        qs = RosterEntry.objects.select_related("player", "team", "season")
        params = self.request.query_params
        if params.get("team"):
            qs = qs.filter(team__slug=params["team"])
        if params.get("season"):
            qs = qs.filter(season__slug=params["season"])
        return qs
