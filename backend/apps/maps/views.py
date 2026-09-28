"""Maps: public reads for drawing; the Super Admin uploads images and calibrates."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.results.models import MatchEvent
from common.permissions import IsSuperAdmin

from . import calibration
from .models import CalibrationPoint, Map, MapArea
from .serializers import (
    CalibrationPointSerializer,
    MapAdminSerializer,
    MapAreaSerializer,
    MapSerializer,
)

MAX_REFERENCE_POINTS = 5000


class MapViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = MapSerializer
    lookup_field = "slug"
    queryset = Map.objects.filter(is_active=True).prefetch_related("areas")


class MapAdminViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Edit maps and upload their images (multipart ``image``). Maps are seeded."""

    permission_classes = [IsSuperAdmin]
    serializer_class = MapAdminSerializer
    lookup_field = "slug"
    queryset = Map.objects.prefetch_related("areas")
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def perform_update(self, serializer):
        image_changed = "image" in serializer.validated_data
        map_ = serializer.save()
        if image_changed:
            # Old clicks were on the old image; start calibration again.
            map_.calibration_points.all().delete()
            map_.recalibrate()

    @action(detail=True, url_path="reference-points")
    def reference_points(self, request, slug=None):
        """Where fights happened on this map (world x, z), to line the image up with."""
        map_ = self.get_object()
        rows = (
            MatchEvent.objects.filter(
                match__map=map_,
                kind__in=[MatchEvent.Kind.KILL, MatchEvent.Kind.DEATH],
                x__isnull=False,
            )
            .order_by("-match_id", "pk")
            .values_list("x", "z", "kind")[:MAX_REFERENCE_POINTS]
        )
        return Response(
            {"map": map_.slug, "points": [{"x": x, "z": z, "kind": k} for x, z, k in rows]}
        )


class _MapChildMixin:
    permission_classes = [IsSuperAdmin]

    def get_map(self) -> Map:
        if not hasattr(self, "_map"):
            self._map = get_object_or_404(Map, slug=self.kwargs["map_slug"])
        return self._map

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "map": self.get_map()}


class CalibrationPointViewSet(_MapChildMixin, viewsets.ModelViewSet):
    """Calibration points; every change refits the map. ``PUT`` on the list replaces all."""

    serializer_class = CalibrationPointSerializer
    pagination_class = None

    def get_queryset(self):
        return CalibrationPoint.objects.filter(map=self.get_map())

    def get_serializer_context(self):
        context = super().get_serializer_context()
        points = list(self.get_queryset().order_by("pk"))
        try:
            result = calibration.fit(
                [calibration.Point(p.world_x, p.world_z, p.pixel_x, p.pixel_y) for p in points]
            )
            context["errors"] = {
                p.pk: round(r, 2) for p, r in zip(points, result.residuals, strict=True)
            }
        except calibration.CalibrationError:
            context["errors"] = {}
        return context

    def list(self, request, *args, **kwargs):
        return Response(self._state())

    def _state(self) -> dict:
        map_ = self.get_map()
        map_.refresh_from_db()
        points = self.get_serializer(self.get_queryset().order_by("pk"), many=True).data
        return {
            "transform": map_.transform,
            "calibration_error": map_.calibration_error,
            "calibrated_at": map_.calibrated_at,
            "points": points,
        }

    def perform_create(self, serializer):
        serializer.save(map=self.get_map())
        self.get_map().recalibrate()

    def perform_update(self, serializer):
        serializer.save()
        self.get_map().recalibrate()

    def perform_destroy(self, instance):
        instance.delete()
        self.get_map().recalibrate()

    def replace(self, request, map_slug=None):
        """Replace every point at once (the overlay tool saves its anchors this way)."""
        items = request.data.get("points") if isinstance(request.data, dict) else None
        if not isinstance(items, list) or len(items) > 50:
            return Response(
                {"points": "A list of up to 50 points."}, status=status.HTTP_400_BAD_REQUEST
            )
        serializer = self.get_serializer(data=items, many=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            self.get_queryset().delete()
            serializer.save(map=self.get_map())
            self.get_map().recalibrate()
        return Response(self._state())


class MapAreaViewSet(_MapChildMixin, viewsets.ModelViewSet):
    """Named areas. Changing them re-labels the rotation points already on this map."""

    serializer_class = MapAreaSerializer
    pagination_class = None

    def get_queryset(self):
        return MapArea.objects.filter(map=self.get_map())

    def perform_create(self, serializer):
        serializer.save(map=self.get_map())
        relabel_points(self.get_map())

    def perform_update(self, serializer):
        serializer.save()
        relabel_points(self.get_map())

    def perform_destroy(self, instance):
        instance.delete()
        relabel_points(self.get_map())


def relabel_points(map_: Map) -> int:
    """Set the area of every rotation point on this map. Returns points changed."""
    from apps.rotations.models import RotationPoint

    areas = list(MapArea.objects.filter(map=map_))
    changed = []
    for point in RotationPoint.objects.filter(rotation__match__map=map_):
        area = MapArea.find(None, point.x, point.z, areas=areas)
        if point.area_id != (area.pk if area else None):
            point.area = area
            changed.append(point)
    RotationPoint.objects.bulk_update(changed, ["area"])
    return len(changed)
