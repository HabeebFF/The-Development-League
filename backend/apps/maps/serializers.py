import math

from rest_framework import serializers

from .models import CalibrationPoint, Map, MapArea

MAX_POLYGON_POINTS = 200


def _finite(value: float, field: str) -> float:
    if not math.isfinite(value) or abs(value) > 1e6:
        raise serializers.ValidationError({field: "Out of range."})
    return value


class MapAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapArea
        fields = ["id", "name", "polygon", "centre_x", "centre_z"]
        read_only_fields = ["centre_x", "centre_z"]
        validators = []

    def validate_polygon(self, value):
        if not isinstance(value, list) or not 3 <= len(value) <= MAX_POLYGON_POINTS:
            raise serializers.ValidationError(f"A list of 3 to {MAX_POLYGON_POINTS} [x, z] points.")
        out = []
        for point in value:
            if (
                not isinstance(point, list | tuple)
                or len(point) != 2
                or not all(isinstance(v, int | float) and not isinstance(v, bool) for v in point)
            ):
                raise serializers.ValidationError("Each point is [x, z] numbers.")
            out.append([_finite(float(point[0]), "polygon"), _finite(float(point[1]), "polygon")])
        return out

    def validate(self, attrs):
        map_ = self.context["map"]
        name = attrs.get("name", getattr(self.instance, "name", None))
        clash = MapArea.objects.filter(map=map_, name=name)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(
                {"name": "This map already has an area with this name."}
            )
        return attrs


class MapSerializer(serializers.ModelSerializer):
    """What the site needs to draw a map: image, size, transform and named areas."""

    areas = MapAreaSerializer(many=True, read_only=True)
    is_calibrated = serializers.SerializerMethodField()

    class Meta:
        model = Map
        fields = [
            "id",
            "name",
            "slug",
            "game_map_id",
            "image",
            "image_width",
            "image_height",
            "transform",
            "is_calibrated",
            "areas",
        ]

    def get_is_calibrated(self, map_: Map) -> bool:
        return bool(map_.transform and map_.image)

    def to_representation(self, map_: Map):
        data = super().to_representation(map_)
        # The storage URL as is: "/media/..." locally (same origin as the site, which
        # the map canvas needs) or the S3 URL in production.
        data["image"] = map_.image.url if map_.image else None
        return data


class MapAdminSerializer(MapSerializer):
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta(MapSerializer.Meta):
        fields = [
            *MapSerializer.Meta.fields,
            "is_active",
            "calibration_error",
            "calibrated_at",
        ]
        read_only_fields = [
            "image_width",
            "image_height",
            "transform",
            "calibration_error",
            "calibrated_at",
        ]


class CalibrationPointSerializer(serializers.ModelSerializer):
    error_px = serializers.SerializerMethodField()

    class Meta:
        model = CalibrationPoint
        fields = ["id", "label", "world_x", "world_z", "pixel_x", "pixel_y", "error_px"]

    def get_error_px(self, point: CalibrationPoint):
        return self.context.get("errors", {}).get(point.pk)

    def validate(self, attrs):
        for field in ["world_x", "world_z", "pixel_x", "pixel_y"]:
            if field in attrs:
                _finite(attrs[field], field)
        map_ = self.context["map"]
        for field, limit in (("pixel_x", map_.image_width), ("pixel_y", map_.image_height)):
            value = attrs.get(field)
            if value is not None and limit and not 0 <= value <= limit:
                raise serializers.ValidationError({field: f"Must be inside the image (0-{limit})."})
        return attrs
