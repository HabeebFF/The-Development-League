import math

from rest_framework import serializers

from apps.league.serializers import TeamRefSerializer
from apps.results.models import ZonePhase

from .models import SINGLE_CHECKPOINTS, Checkpoint, RotationPoint, TeamRotation

MAX_POINTS = 60
WORLD_LIMIT = 5000.0  # well beyond any map edge


class RotationPointSerializer(serializers.ModelSerializer):
    area = serializers.CharField(source="area.name", read_only=True, default=None)

    class Meta:
        model = RotationPoint
        fields = ["checkpoint", "x", "z", "game_time_s", "area", "source", "evidence", "note"]
        read_only_fields = ["source", "evidence"]

    def validate_x(self, value: float) -> float:
        return _world(value)

    def validate_z(self, value: float) -> float:
        return _world(value)

    def validate_game_time_s(self, value):
        if value is not None and not 0 <= value <= 7200:
            raise serializers.ValidationError("Seconds from match start (0-7200).")
        return value


def _world(value: float) -> float:
    if not math.isfinite(value) or abs(value) > WORLD_LIMIT:
        raise serializers.ValidationError(
            f"World coordinate between -{WORLD_LIMIT:g} and {WORLD_LIMIT:g}."
        )
    return value


class RotationSaveSerializer(serializers.Serializer):
    """The plotting tool's full replace: every point of one team in one match."""

    points = RotationPointSerializer(many=True)

    def validate_points(self, points: list[dict]) -> list[dict]:
        if len(points) > MAX_POINTS:
            raise serializers.ValidationError(f"At most {MAX_POINTS} points.")
        seen = set()
        for p in points:
            checkpoint = p["checkpoint"]
            if checkpoint in SINGLE_CHECKPOINTS and checkpoint in seen:
                label = Checkpoint(checkpoint).label
                raise serializers.ValidationError(f"{label} can only be plotted once.")
            seen.add(checkpoint)
        if {Checkpoint.FINAL, Checkpoint.ELIMINATED} <= seen:
            raise serializers.ValidationError("A team is either eliminated or finishes, not both.")
        return points


class TeamRotationSerializer(serializers.ModelSerializer):
    team = TeamRefSerializer(read_only=True)
    placement = serializers.SerializerMethodField()
    points = RotationPointSerializer(many=True, read_only=True)
    plotted_by = serializers.StringRelatedField()

    class Meta:
        model = TeamRotation
        fields = [
            "team",
            "placement",
            "status",
            "plotted_by",
            "confirmed_at",
            "updated_at",
            "points",
        ]

    def get_placement(self, rotation: TeamRotation) -> int | None:
        return self.context.get("placements", {}).get(rotation.team_id)


class ZonePhaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ZonePhase
        fields = [
            "stage_index",
            "state",
            "game_time_s",
            "outer_x",
            "outer_z",
            "outer_radius",
            "inner_x",
            "inner_z",
            "inner_radius",
        ]
