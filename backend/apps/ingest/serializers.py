from django.conf import settings
from rest_framework import serializers

from apps.league.models import Match, MatchDay, Team
from apps.maps.models import Map

from .models import ParseRun, UploadBatch, UploadedFile
from .services import storage


class UploadedFileSerializer(serializers.ModelSerializer):
    game_match_id = serializers.CharField(read_only=True, allow_null=True)

    class Meta:
        model = UploadedFile
        fields = [
            "id",
            "original_name",
            "kind",
            "game_match_id",
            "file_timestamp",
            "size",
            "parse_status",
            "parse_report",
            "created_at",
        ]


class UploadBatchSerializer(serializers.ModelSerializer):
    files = UploadedFileSerializer(many=True, read_only=True)
    uploaded_by = serializers.StringRelatedField()

    class Meta:
        model = UploadBatch
        fields = ["id", "status", "note", "uploaded_by", "preview", "error", "files", "created_at"]
        read_only_fields = ["status", "preview", "error", "files", "uploaded_by", "created_at"]


class UploadBatchListSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.StringRelatedField()
    file_count = serializers.IntegerField(source="files.count", read_only=True)

    class Meta:
        model = UploadBatch
        fields = ["id", "status", "note", "uploaded_by", "file_count", "created_at"]


class FileSpecSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    size = serializers.IntegerField(min_value=0)

    def validate_size(self, value: int) -> int:
        if value > settings.UPLOAD_MAX_FILE_BYTES:
            raise serializers.ValidationError("File is too large.")
        return value


class PresignSerializer(serializers.Serializer):
    files = FileSpecSerializer(many=True, allow_empty=False)


class RegisteredFileSerializer(FileSpecSerializer):
    key = serializers.CharField(max_length=500)


class RegisterSerializer(serializers.Serializer):
    files = RegisteredFileSerializer(many=True, allow_empty=False)

    def validate_files(self, files):
        batch = self.context["batch"]
        for f in files:
            if not storage.key_belongs_to_batch(f["key"], batch.pk):
                raise serializers.ValidationError(f"{f['name']}: key is not from this batch.")
        return files


class AssignmentSerializer(serializers.Serializer):
    game_match_id = serializers.CharField()
    match_day = serializers.PrimaryKeyRelatedField(
        queryset=MatchDay.objects.all(), required=False, allow_null=True
    )
    number = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    map = serializers.PrimaryKeyRelatedField(
        queryset=Map.objects.all(), required=False, allow_null=True
    )
    teams = serializers.DictField(
        child=serializers.PrimaryKeyRelatedField(queryset=Team.objects.all()),
        required=False,
        help_text="In-game team name -> league team id",
    )
    create_missing_teams = serializers.BooleanField(default=True)

    def validate_game_match_id(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError("Must be the numeric game match id.")
        return value

    def validate(self, attrs):
        exists = Match.objects.filter(game_match_id=int(attrs["game_match_id"])).exists()
        if not exists and (not attrs.get("match_day") or not attrs.get("number")):
            raise serializers.ValidationError("A new match needs match_day and number.")
        return attrs

    def to_task_payload(self, attrs) -> dict:
        return {
            "game_match_id": attrs["game_match_id"],
            "match_day": attrs["match_day"].pk if attrs.get("match_day") else None,
            "number": attrs.get("number"),
            "map": attrs["map"].pk if attrs.get("map") else None,
            "teams": {name: team.pk for name, team in (attrs.get("teams") or {}).items()},
            "create_missing_teams": attrs["create_missing_teams"],
        }


class ConfirmSerializer(serializers.Serializer):
    matches = AssignmentSerializer(many=True, allow_empty=False)

    def validate_matches(self, matches):
        batch = self.context["batch"]
        in_preview = {m["game_match_id"] for m in batch.preview.get("matches", [])}
        seen_ids, seen_slots = set(), set()
        for m in matches:
            gid = m["game_match_id"]
            if gid not in in_preview:
                raise serializers.ValidationError(f"Match {gid} is not in this batch.")
            if gid in seen_ids:
                raise serializers.ValidationError(f"Match {gid} is listed twice.")
            seen_ids.add(gid)
            if m.get("match_day") and m.get("number"):
                slot = (m["match_day"].pk, m["number"])
                if slot in seen_slots:
                    raise serializers.ValidationError(
                        f"Two matches share match day {slot[0]} number {slot[1]}."
                    )
                seen_slots.add(slot)
        return matches


class ParseRunSerializer(serializers.ModelSerializer):
    triggered_by = serializers.StringRelatedField()

    class Meta:
        model = ParseRun
        fields = [
            "id",
            "status",
            "batch",
            "triggered_by",
            "sources",
            "counts",
            "warnings",
            "error",
            "created_at",
            "finished_at",
        ]
