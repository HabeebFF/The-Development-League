import re

from rest_framework import serializers

from .models import Player, RosterEntry, Season, Team, TeamAlias

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
SOCIAL_KEYS = {"instagram", "x", "tiktok", "youtube", "discord", "facebook", "website"}


class PlayerRefSerializer(serializers.ModelSerializer):
    game_uid = serializers.CharField(read_only=True)

    class Meta:
        model = Player
        fields = ["id", "game_uid", "display_name"]


class RosterEntrySerializer(serializers.ModelSerializer):
    player = PlayerRefSerializer(read_only=True)
    player_uid = serializers.CharField(write_only=True)
    team = serializers.SlugRelatedField(slug_field="slug", queryset=Team.objects.all())
    season = serializers.SlugRelatedField(slug_field="slug", queryset=Season.objects.all())

    class Meta:
        model = RosterEntry
        fields = ["id", "player", "player_uid", "team", "season", "role", "joined_on", "left_on"]

    def validate_player_uid(self, value: str) -> Player:
        if not value.strip().isdigit():
            raise serializers.ValidationError("A game UID is digits only.")
        player = Player.objects.filter(game_uid=int(value)).first()
        if player is None:
            raise serializers.ValidationError("No player with this UID yet.")
        return player

    def validate(self, attrs):
        if "player_uid" in attrs:
            attrs["player"] = attrs.pop("player_uid")
        player = attrs.get("player", getattr(self.instance, "player", None))
        season = attrs.get("season", getattr(self.instance, "season", None))
        left_on = attrs.get("left_on", getattr(self.instance, "left_on", None))
        if left_on is None and player and season:
            clash = RosterEntry.objects.filter(player=player, season=season, left_on__isnull=True)
            if self.instance:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError(
                    "This player is already on a roster this season; set left_on there first."
                )
        return attrs


class TeamPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = [
            "id",
            "name",
            "tag",
            "slug",
            "logo",
            "primary_color",
            "secondary_color",
            "socials",
        ]


class TeamDetailSerializer(TeamPublicSerializer):
    roster = serializers.SerializerMethodField()

    class Meta(TeamPublicSerializer.Meta):
        fields = [*TeamPublicSerializer.Meta.fields, "roster"]

    def get_roster(self, team: Team):
        season = Season.objects.filter(is_active=True).first()
        if season is None:
            return []
        entries = team.roster_entries.filter(season=season, left_on__isnull=True).select_related(
            "player"
        )
        return [
            {
                "player": PlayerRefSerializer(e.player).data,
                "role": e.role,
                "joined_on": e.joined_on,
            }
            for e in entries
        ]


class TeamAdminSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(required=False)
    aliases = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = [
            "id",
            "name",
            "tag",
            "slug",
            "logo",
            "primary_color",
            "secondary_color",
            "socials",
            "is_league_member",
            "plan",
            "aliases",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def get_aliases(self, team: Team) -> list[str]:
        return list(team.aliases.values_list("in_game_name", flat=True))

    def validate_primary_color(self, value: str) -> str:
        return self._color(value)

    def validate_secondary_color(self, value: str) -> str:
        return self._color(value)

    def _color(self, value: str) -> str:
        if value and not _HEX.match(value):
            raise serializers.ValidationError("Use #RRGGBB.")
        return value.upper()

    def validate_socials(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('Must be an object like {"instagram": "url"}.')
        unknown = set(value) - SOCIAL_KEYS
        if unknown:
            raise serializers.ValidationError(f"Unknown networks: {sorted(unknown)}")
        for key, url in value.items():
            if not isinstance(url, str) or not url.startswith(("https://", "http://")):
                raise serializers.ValidationError(f"{key}: must be a link.")
        return value


class TeamAliasSerializer(serializers.ModelSerializer):
    team = serializers.SlugRelatedField(slug_field="slug", queryset=Team.objects.all())
    season = serializers.SlugRelatedField(
        slug_field="slug", queryset=Season.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = TeamAlias
        fields = ["id", "in_game_name", "team", "season"]
        validators = []  # uniqueness checked below with a clear message

    def validate(self, attrs):
        name = attrs.get("in_game_name", getattr(self.instance, "in_game_name", None))
        season = attrs.get("season", getattr(self.instance, "season", None))
        clash = TeamAlias.objects.filter(in_game_name=name, season=season)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(f"'{name}' is already mapped for this season.")
        return attrs


class PlayerAdminSerializer(serializers.ModelSerializer):
    game_uid = serializers.CharField(read_only=True)
    current_team = serializers.SlugRelatedField(
        slug_field="slug", queryset=Team.objects.all(), required=False, allow_null=True
    )
    user = serializers.EmailField(source="user.email", read_only=True, allow_null=True)

    class Meta:
        model = Player
        fields = [
            "id",
            "game_uid",
            "current_name_raw",
            "display_name",
            "current_team",
            "country",
            "user",
        ]
        read_only_fields = ["current_name_raw"]
