from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.league.models import Team
from apps.results.models import MatchEvent
from common.permissions import IsStaff

from .engine import team_profile
from .models import KnowledgeEntry, WeaponName
from .serializers import KnowledgeEntrySerializer, WeaponNameSerializer


class KnowledgeEntryViewSet(viewsets.ModelViewSet):
    """The coach's knowledge base. Filter with ``?kind=`` and ``?map=<slug>``."""

    permission_classes = [IsStaff]
    serializer_class = KnowledgeEntrySerializer
    pagination_class = None

    def get_queryset(self):
        qs = KnowledgeEntry.objects.select_related("map", "area", "updated_by")
        if kind := self.request.query_params.get("kind"):
            qs = qs.filter(kind=kind)
        if map_slug := self.request.query_params.get("map"):
            qs = qs.filter(map__slug=map_slug)
        return qs

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class WeaponListView(APIView):
    """Every weapon number seen in kills or knocks, how often, and its name if staff gave one."""

    permission_classes = [IsStaff]

    def get(self, request):
        seen = (
            MatchEvent.objects.filter(weapon_id__isnull=False)
            .values("weapon_id")
            .annotate(
                kills=Count("id", filter=Q(kind=MatchEvent.Kind.KILL)),
                knocks=Count("id", filter=Q(kind=MatchEvent.Kind.KNOCK)),
            )
        )
        rows = {r["weapon_id"]: {**r, "name": "", "weapon_class": "", "note": ""} for r in seen}
        for w in WeaponName.objects.all():
            row = rows.setdefault(w.weapon_id, {"weapon_id": w.weapon_id, "kills": 0, "knocks": 0})
            row.update(WeaponNameSerializer(w).data)
        return Response(
            sorted(rows.values(), key=lambda r: (-(r["kills"] + r["knocks"]), r["weapon_id"]))
        )


class WeaponNameView(generics.GenericAPIView):
    """``PUT`` names a weapon number; ``DELETE`` forgets the name."""

    permission_classes = [IsStaff]
    serializer_class = WeaponNameSerializer

    def put(self, request, weapon_id: int):
        instance = WeaponName.objects.filter(weapon_id=weapon_id).first()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(weapon_id=weapon_id)
        return Response(
            serializer.data, status=status.HTTP_200_OK if instance else status.HTTP_201_CREATED
        )

    def delete(self, request, weapon_id: int):
        WeaponName.objects.filter(weapon_id=weapon_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TeamProfileView(APIView):
    """What the analysis engine found about a team: facts with the matches behind them.
    Staff only for now; teams get their own reports in a later step."""

    permission_classes = [IsStaff]

    def get(self, request, slug: str):
        team = get_object_or_404(Team, slug=slug)
        return Response({"team": team.name, **team_profile(team.pk)})
