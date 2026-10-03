from rest_framework import serializers

from apps.maps.models import Map, MapArea

from .models import KnowledgeEntry, WeaponName


class KnowledgeEntrySerializer(serializers.ModelSerializer):
    map = serializers.SlugRelatedField(
        slug_field="slug", queryset=Map.objects.all(), allow_null=True, required=False
    )
    area = serializers.PrimaryKeyRelatedField(
        queryset=MapArea.objects.all(), allow_null=True, required=False
    )
    area_name = serializers.CharField(source="area.name", read_only=True, default=None)
    updated_by = serializers.EmailField(source="updated_by.email", read_only=True, default=None)

    class Meta:
        model = KnowledgeEntry
        fields = [
            "id",
            "kind",
            "title",
            "body",
            "data",
            "map",
            "area",
            "area_name",
            "updated_by",
            "updated_at",
        ]

    def validate_data(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("An object of named values.")
        return value

    def validate(self, attrs):
        area = attrs.get("area", getattr(self.instance, "area", None))
        map_ = attrs.get("map", getattr(self.instance, "map", None))
        if area is not None:
            if map_ is None:
                attrs["map"] = map_ = area.map
            if area.map_id != map_.pk:
                raise serializers.ValidationError({"area": "That area is on another map."})
        return attrs


class WeaponNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeaponName
        fields = ["weapon_id", "name", "weapon_class", "note"]
        read_only_fields = ["weapon_id"]
