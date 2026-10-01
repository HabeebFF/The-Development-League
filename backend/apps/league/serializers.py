import re

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.maps.models import Map
from apps.results.models import PlayerMatchResult, StandingRow, TeamMatchResult

from .models import (
    TIEBREAKER_CHOICES,
    Group,
    Match,
    MatchDay,
    Player,
    RosterEntry,
    ScoringRule,
    Season,
    Stage,
    Team,
    TeamAlias,
)

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
    matches_played = serializers.IntegerField(read_only=True, default=0)

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
            "matches_played",
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


# -- seasons, stages, groups, match days, matches ---------------------------------------------


class TeamRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "name", "tag", "slug", "logo", "primary_color"]


class ScoringRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScoringRule
        fields = ["id", "name", "placement_points", "default_points", "points_per_kill"]

    def validate(self, attrs):
        instance = ScoringRule(**{**self._current(), **attrs})
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return attrs

    def _current(self) -> dict:
        if self.instance is None:
            return {}
        return {
            f: getattr(self.instance, f)
            for f in ["name", "placement_points", "default_points", "points_per_kill"]
        }


class GroupPublicSerializer(serializers.ModelSerializer):
    teams = TeamRefSerializer(many=True, read_only=True)

    class Meta:
        model = Group
        fields = ["id", "name", "teams"]


class StagePublicSerializer(serializers.ModelSerializer):
    groups = GroupPublicSerializer(many=True, read_only=True)

    class Meta:
        model = Stage
        fields = ["id", "name", "order", "kind", "groups"]


class SeasonListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Season
        fields = ["id", "name", "slug", "starts_on", "ends_on", "is_active"]


class SeasonDetailSerializer(SeasonListSerializer):
    scoring = ScoringRuleSerializer(source="scoring_rule", read_only=True)
    stages = StagePublicSerializer(many=True, read_only=True)

    class Meta(SeasonListSerializer.Meta):
        fields = [*SeasonListSerializer.Meta.fields, "scoring", "tiebreakers", "stages"]


class StandingRowSerializer(serializers.ModelSerializer):
    team = TeamRefSerializer(read_only=True)

    class Meta:
        model = StandingRow
        fields = [
            "rank",
            "team",
            "matches_played",
            "booyahs",
            "kills",
            "placement_points",
            "kill_points",
            "total_points",
            "avg_placement",
            "last_match_points",
            "form",
        ]


class MatchSummarySerializer(serializers.ModelSerializer):
    """A match inside a fixture list or match day: what, when, where, and who won."""

    map = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    played = serializers.SerializerMethodField()
    booyah = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            "id",
            "number",
            "map",
            "scheduled_at",
            "started_at",
            "played",
            "booyah",
            "vod_url",
        ]

    def get_played(self, match: Match) -> bool:
        return match.status == Match.Status.PUBLISHED

    def get_booyah(self, match: Match):
        if match.status != Match.Status.PUBLISHED:
            return None
        winner = next((r for r in match.team_results.all() if r.placement == 1), None)
        return TeamRefSerializer(winner.team, context=self.context).data if winner else None


class MatchDaySerializer(serializers.ModelSerializer):
    stage = serializers.CharField(source="stage.name", read_only=True)
    group = serializers.CharField(source="group.name", read_only=True, default=None)
    matches = MatchSummarySerializer(many=True, read_only=True)

    class Meta:
        model = MatchDay
        fields = ["id", "number", "title", "date", "stage", "group", "matches"]


class PlayerResultSerializer(serializers.ModelSerializer):
    game_uid = serializers.CharField(source="player.game_uid", read_only=True)

    class Meta:
        model = PlayerMatchResult
        fields = [
            "game_uid",
            "display_name",
            "kills",
            "knocks",
            "headshot_knocks",
            "deaths",
            "respawns",
            "is_mvp",
        ]


class TeamResultSerializer(serializers.ModelSerializer):
    team = TeamRefSerializer(read_only=True)
    booyah = serializers.BooleanField(source="is_booyah", read_only=True)
    players = serializers.SerializerMethodField()

    class Meta:
        model = TeamMatchResult
        fields = [
            "placement",
            "team",
            "in_game_name",
            "booyah",
            "kills",
            "placement_points",
            "kill_points",
            "total_points",
            "eliminated_at_s",
            "players",
        ]

    def get_players(self, result: TeamMatchResult):
        players = self.context.get("players_by_team", {}).get(result.team_id, [])
        return PlayerResultSerializer(players, many=True).data


class MatchListSerializer(MatchSummarySerializer):
    season = serializers.SlugRelatedField(
        source="match_day.stage.season", slug_field="slug", read_only=True
    )
    match_day = serializers.IntegerField(source="match_day_id", read_only=True)

    class Meta(MatchSummarySerializer.Meta):
        fields = ["season", "match_day", *MatchSummarySerializer.Meta.fields]


class MatchDetailSerializer(MatchListSerializer):
    game_match_id = serializers.CharField(read_only=True)
    results = serializers.SerializerMethodField()

    class Meta(MatchListSerializer.Meta):
        fields = [*MatchListSerializer.Meta.fields, "game_match_id", "duration_s", "results"]

    def get_results(self, match: Match):
        by_team: dict[int, list] = {}
        for p in match.player_results.select_related("player").order_by("-kills", "display_name"):
            by_team.setdefault(p.team_id, []).append(p)
        results = match.team_results.select_related("team").order_by("placement")
        context = {**self.context, "players_by_team": by_team}
        return TeamResultSerializer(results, many=True, context=context).data


# -- staff (admin) serializers -----------------------------------------------------------------


class SeasonAdminSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(required=False)
    scoring_rule = serializers.PrimaryKeyRelatedField(
        queryset=ScoringRule.objects.all(), required=False
    )

    class Meta:
        model = Season
        fields = [
            "id",
            "name",
            "slug",
            "starts_on",
            "ends_on",
            "is_active",
            "scoring_rule",
            "tiebreakers",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate_tiebreakers(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError(f"A non-empty list from {TIEBREAKER_CHOICES}.")
        bad = [t for t in value if t not in TIEBREAKER_CHOICES]
        if bad:
            raise serializers.ValidationError(f"Unknown tiebreakers: {bad}")
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Each tiebreaker can appear once.")
        return value

    def validate(self, attrs):
        starts = attrs.get("starts_on", getattr(self.instance, "starts_on", None))
        ends = attrs.get("ends_on", getattr(self.instance, "ends_on", None))
        if starts and ends and ends < starts:
            raise serializers.ValidationError({"ends_on": "Ends before it starts."})
        if self.instance is None and "scoring_rule" not in attrs:
            default = ScoringRule.objects.filter(name="TDL default").first()
            if default is None:
                raise serializers.ValidationError({"scoring_rule": "Pick a scoring rule."})
            attrs["scoring_rule"] = default
        return attrs


class StageAdminSerializer(serializers.ModelSerializer):
    season = serializers.SlugRelatedField(slug_field="slug", queryset=Season.objects.all())

    class Meta:
        model = Stage
        fields = ["id", "season", "name", "order", "kind"]
        validators = []

    def validate(self, attrs):
        season = attrs.get("season", getattr(self.instance, "season", None))
        name = attrs.get("name", getattr(self.instance, "name", None))
        clash = Stage.objects.filter(season=season, name=name)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(
                {"name": "This season already has a stage with this name."}
            )
        return attrs


class GroupAdminSerializer(serializers.ModelSerializer):
    stage = serializers.PrimaryKeyRelatedField(queryset=Stage.objects.all())
    teams = serializers.SlugRelatedField(
        slug_field="slug", queryset=Team.objects.all(), many=True, required=False
    )

    class Meta:
        model = Group
        fields = ["id", "stage", "name", "teams"]
        validators = []

    def validate(self, attrs):
        stage = attrs.get("stage", getattr(self.instance, "stage", None))
        name = attrs.get("name", getattr(self.instance, "name", None))
        clash = Group.objects.filter(stage=stage, name=name)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(
                {"name": "This stage already has a group with this name."}
            )
        teams = attrs.get("teams")
        if teams:
            taken = (
                Team.objects.filter(pk__in=[t.pk for t in teams], league_groups__stage=stage)
                .exclude(league_groups=self.instance)
                .values_list("name", flat=True)
                .distinct()
            )
            if taken:
                raise serializers.ValidationError(
                    {"teams": f"Already in another group of this stage: {sorted(taken)}"}
                )
        return attrs


class MatchDayAdminSerializer(serializers.ModelSerializer):
    stage = serializers.PrimaryKeyRelatedField(queryset=Stage.objects.all())
    group = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = MatchDay
        fields = ["id", "stage", "group", "number", "date", "title"]
        validators = []

    def validate(self, attrs):
        stage = attrs.get("stage", getattr(self.instance, "stage", None))
        group = attrs.get("group", getattr(self.instance, "group", None))
        number = attrs.get("number", getattr(self.instance, "number", None))
        if group is not None and group.stage_id != stage.pk:
            raise serializers.ValidationError({"group": "This group belongs to another stage."})
        clash = MatchDay.objects.filter(stage=stage, group=group, number=number)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError({"number": "This match day number is taken."})
        return attrs


class MatchAdminSerializer(serializers.ModelSerializer):
    match_day = serializers.PrimaryKeyRelatedField(queryset=MatchDay.objects.all())
    map = serializers.SlugRelatedField(
        slug_field="slug", queryset=Map.objects.all(), required=False, allow_null=True
    )
    game_match_id = serializers.CharField(read_only=True)
    has_results = serializers.SerializerMethodField()
    label = serializers.CharField(source="__str__", read_only=True)
    rotations = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            "id",
            "label",
            "match_day",
            "number",
            "map",
            "scheduled_at",
            "status",
            "vod_url",
            "room_name",
            "game_match_id",
            "started_at",
            "duration_s",
            "has_results",
            "rotations",
        ]
        read_only_fields = ["started_at", "duration_s"]
        validators = []

    def get_has_results(self, match: Match) -> bool:
        return match.team_results.exists()

    def get_rotations(self, match: Match) -> dict[str, int]:
        """How far plotting has got: rotations per status (AUTO, DRAFT, CONFIRMED)."""
        counts = {"AUTO": 0, "DRAFT": 0, "CONFIRMED": 0}
        for rotation in match.rotations.all():
            counts[rotation.status] += 1
        return counts

    def validate_status(self, value: str) -> str:
        allowed = {Match.Status.DRAFT, Match.Status.NEEDS_REVIEW, Match.Status.PUBLISHED}
        if value not in allowed:
            raise serializers.ValidationError("Processing is set by the upload flow only.")
        if value == Match.Status.PUBLISHED and not (
            self.instance and self.instance.team_results.exists()
        ):
            raise serializers.ValidationError("Upload this match's logs before publishing it.")
        return value

    def validate(self, attrs):
        day = attrs.get("match_day", getattr(self.instance, "match_day", None))
        number = attrs.get("number", getattr(self.instance, "number", None))
        clash = Match.objects.filter(match_day=day, number=number)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError({"number": f"{day} already has a match {number}."})
        return attrs
