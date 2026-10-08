from rest_framework import serializers

from apps.maps.models import Map, MapArea

from .models import CoachReport, CounterPlan, KnowledgeEntry, WeaponName


class KnowledgeEntrySerializer(serializers.ModelSerializer):
    map = serializers.SlugRelatedField(
        slug_field="slug", queryset=Map.objects.all(), allow_null=True, required=False
    )
    area = serializers.PrimaryKeyRelatedField(
        queryset=MapArea.objects.all(), allow_null=True, required=False
    )
    area_name = serializers.CharField(source="area.name", read_only=True, default=None)
    area_status = serializers.CharField(source="area.status", read_only=True, default=None)
    updated_by = serializers.EmailField(source="updated_by.email", read_only=True, default=None)
    reviewed_by = serializers.EmailField(source="reviewed_by.email", read_only=True, default=None)

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
            "area_status",
            "status",
            "origin",
            "sources",
            "patch",
            "conflicts",
            "weak_sources",
            "weak_reason",
            "updated_by",
            "updated_at",
            "reviewed_by",
            "reviewed_at",
        ]
        read_only_fields = ["origin", "weak_sources", "weak_reason", "reviewed_at"]

    def validate_sources(self, value):
        if not isinstance(value, list) or not all(
            isinstance(s, dict) and isinstance(s.get("url", ""), str) for s in value
        ):
            raise serializers.ValidationError("A list of {title, url, published} sources.")
        return value

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


class CoachReportSerializer(serializers.ModelSerializer):
    team = serializers.CharField(source="team.name", read_only=True)
    team_slug = serializers.CharField(source="team.slug", read_only=True)
    edited_by = serializers.EmailField(source="edited_by.email", read_only=True, default=None)

    class Meta:
        model = CoachReport
        fields = [
            "id",
            "team",
            "team_slug",
            "week_start",
            "matches",
            "facts",
            "tasks",
            "changes",
            "writer",
            "is_published",
            "edited_by",
            "updated_at",
        ]
        read_only_fields = ["week_start", "matches", "facts", "changes", "writer"]

    def validate_tasks(self, value):
        """Staff may reword, drop or reorder tasks, but each must still cite real facts."""
        facts = {f["id"] for f in (self.instance.facts if self.instance else [])}
        if not isinstance(value, list) or len(value) > 8:
            raise serializers.ValidationError("A list of up to 8 tasks.")
        out = []
        for t in value:
            if not isinstance(t, dict) or not str(t.get("title", "")).strip():
                raise serializers.ValidationError("Each task needs a title.")
            cited = t.get("facts") or []
            if not cited or not set(cited) <= facts:
                raise serializers.ValidationError("Each task must cite this report's facts.")
            known = {f["id"]: f for f in self.instance.facts}
            task = {
                "title": str(t["title"]).strip()[:160],
                "why": [known[c]["text"] for c in cited],
                "facts": cited,
                "matches": sorted({m for c in cited for m in known[c]["matches"]}),
            }
            # The AI writer's advice can be reworded or cleared; its knowledge links can
            # only be kept or dropped.
            advice = str(t.get("advice") or "").strip()[:400]
            if advice:
                task["advice"] = advice
            links = {k["id"]: k for old in self.instance.tasks for k in old.get("knowledge", [])}
            kept = [links[k["id"]] for k in t.get("knowledge") or [] if k.get("id") in links]
            if kept:
                task["knowledge"] = kept
            out.append(task)
        return out


class CounterPlanSerializer(serializers.ModelSerializer):
    team = serializers.CharField(source="team.name", read_only=True)
    opponent = serializers.CharField(source="opponent.name", read_only=True)
    opponent_slug = serializers.CharField(source="opponent.slug", read_only=True)

    class Meta:
        model = CounterPlan
        fields = [
            "team",
            "opponent",
            "opponent_slug",
            "week_start",
            "matches",
            "facts",
            "plays",
            "head_to_head",
            "writer",
            "updated_at",
        ]
