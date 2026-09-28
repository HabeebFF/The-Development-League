"""Rotation API: team accounts with rotations.view read; staff plot and confirm."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.league.models import Match, Team
from apps.maps.models import MapArea
from apps.results.models import TeamMatchResult, ZonePhase
from common.permissions import HasFeature, IsStaff

from .auto import draft_rotations
from .models import RotationPoint, TeamRotation
from .serializers import RotationSaveSerializer, TeamRotationSerializer, ZonePhaseSerializer


def _match(request, pk: int) -> Match:
    qs = Match.objects.select_related("map")
    if not request.user.is_league_staff:
        qs = qs.filter(status=Match.Status.PUBLISHED)
    return get_object_or_404(qs, pk=pk)


def _map_info(match: Match) -> dict | None:
    return {"slug": match.map.slug, "name": match.map.name} if match.map else None


class MatchZonesView(APIView):
    permission_classes = [HasFeature("rotations.view")]

    def get(self, request, pk: int):
        match = _match(request, pk)
        zones = ZonePhase.objects.filter(match=match).order_by("stage_index", "game_time_s")
        return Response(
            {
                "match": match.pk,
                "map": _map_info(match),
                "duration_s": match.duration_s,
                "zones": ZonePhaseSerializer(zones, many=True).data,
            }
        )


class MatchRotationsView(APIView):
    """Every team's rotation in a match, best placement first."""

    permission_classes = [HasFeature("rotations.view")]

    def get(self, request, pk: int):
        match = _match(request, pk)
        placements = dict(
            TeamMatchResult.objects.filter(match=match).values_list("team_id", "placement")
        )
        rotations = sorted(
            TeamRotation.objects.filter(match=match)
            .select_related("team", "plotted_by")
            .prefetch_related("points__area"),
            key=lambda r: (placements.get(r.team_id, 99), r.team.name),
        )
        data = TeamRotationSerializer(
            rotations, many=True, context={"request": request, "placements": placements}
        ).data
        return Response({"match": match.pk, "map": _map_info(match), "rotations": data})


class TeamRotationView(APIView):
    """The plotting tool: read one team's rotation, or save all its points (full replace)."""

    permission_classes = [IsStaff]

    def _load(self, pk: int, team_slug: str) -> tuple[Match, TeamRotation, TeamMatchResult]:
        match = get_object_or_404(Match.objects.select_related("map"), pk=pk)
        team = get_object_or_404(Team, slug=team_slug)
        result = TeamMatchResult.objects.filter(match=match, team=team).first()
        if result is None:
            raise ValidationError({"detail": f"{team} did not play this match."})
        rotation = TeamRotation.objects.filter(match=match, team=team).first()
        if rotation is None:
            draft_rotations(match, team_ids={team.pk})
            rotation = TeamRotation.objects.get(match=match, team=team)
        return match, rotation, result

    def _response(self, request, rotation: TeamRotation, result: TeamMatchResult) -> Response:
        rotation = (
            TeamRotation.objects.select_related("team", "plotted_by")
            .prefetch_related("points__area")
            .get(pk=rotation.pk)
        )
        context = {"request": request, "placements": {result.team_id: result.placement}}
        return Response(TeamRotationSerializer(rotation, context=context).data)

    def get(self, request, pk: int, team_slug: str):
        _, rotation, result = self._load(pk, team_slug)
        return self._response(request, rotation, result)

    def put(self, request, pk: int, team_slug: str):
        match, rotation, result = self._load(pk, team_slug)
        serializer = RotationSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        areas = list(MapArea.objects.filter(map_id=match.map_id)) if match.map_id else []
        # A point sent back unchanged keeps where it came from (auto evidence).
        before = {(p.checkpoint, round(p.x, 2), round(p.z, 2)): p for p in rotation.points.all()}
        with transaction.atomic():
            rotation.points.all().delete()
            rows = []
            for order, item in enumerate(serializer.validated_data["points"]):
                x, z = item["x"], item["z"]
                old = before.get((item["checkpoint"], round(x, 2), round(z, 2)))
                rows.append(
                    RotationPoint(
                        rotation=rotation,
                        checkpoint=item["checkpoint"],
                        order=order,
                        x=x,
                        z=z,
                        game_time_s=item.get("game_time_s"),
                        note=item.get("note", ""),
                        area=MapArea.find(None, x, z, areas=areas),
                        source=old.source if old else RotationPoint.Source.MANUAL,
                        evidence=old.evidence if old else {},
                    )
                )
            RotationPoint.objects.bulk_create(rows)
            rotation.status = TeamRotation.Status.DRAFT
            rotation.plotted_by = request.user
            rotation.confirmed_at = None
            rotation.save()
        return self._response(request, rotation, result)


class ConfirmRotationView(TeamRotationView):
    def post(self, request, pk: int, team_slug: str):
        _, rotation, result = self._load(pk, team_slug)
        if not rotation.points.exists():
            raise ValidationError({"detail": "Plot at least one point first."})
        rotation.status = TeamRotation.Status.CONFIRMED
        rotation.confirmed_at = timezone.now()
        if rotation.plotted_by_id is None:
            rotation.plotted_by = request.user
        rotation.save()
        return self._response(request, rotation, result)

    http_method_names = ["post", "options"]


class ResetRotationView(TeamRotationView):
    """Throw away staff edits and go back to the auto draft."""

    def post(self, request, pk: int, team_slug: str):
        match, rotation, result = self._load(pk, team_slug)
        draft_rotations(match, team_ids={rotation.team_id})
        return self._response(request, rotation, result)

    http_method_names = ["post", "options"]


class MatchRedraftView(APIView):
    """Re-run the auto draft for a match (only teams still in AUTO change)."""

    permission_classes = [IsStaff]

    def post(self, request, pk: int):
        match = get_object_or_404(Match, pk=pk)
        drafted = draft_rotations(match)
        return Response({"drafted": drafted}, status=status.HTTP_200_OK)
