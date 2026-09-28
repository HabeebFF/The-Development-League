"""League structure: seasons > stages/groups > match days > matches, plus teams and players.

Standings live in ``results`` (they are computed from match results).
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from common.models import TimeStampedModel

DEFAULT_PLACEMENT_POINTS = {
    "1": 12,
    "2": 9,
    "3": 8,
    "4": 7,
    "5": 6,
    "6": 5,
    "7": 4,
    "8": 3,
    "9": 2,
    "10": 1,
}

TIEBREAKER_CHOICES = ["total_points", "booyahs", "kills", "placement_points", "last_match"]
DEFAULT_TIEBREAKERS = ["total_points", "booyahs", "kills", "placement_points", "last_match"]


def default_placement_points() -> dict[str, int]:
    return dict(DEFAULT_PLACEMENT_POINTS)


def default_tiebreakers() -> list[str]:
    return list(DEFAULT_TIEBREAKERS)


class ScoringRule(TimeStampedModel):
    name = models.CharField(max_length=80, unique=True)
    placement_points = models.JSONField(
        default=default_placement_points,
        help_text='Placement -> points, e.g. {"1": 12, "2": 9}. Missing placements get '
        "default_points.",
    )
    default_points = models.IntegerField(default=0)
    points_per_kill = models.IntegerField(default=1)

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        if not isinstance(self.placement_points, dict):
            raise ValidationError({"placement_points": "Must be an object of placement -> points"})
        for key, value in self.placement_points.items():
            if not str(key).isdigit() or not isinstance(value, int):
                raise ValidationError({"placement_points": f"Bad entry {key!r}: {value!r}"})

    def placement_score(self, placement: int) -> int:
        return int(self.placement_points.get(str(placement), self.default_points))

    def kill_score(self, kills: int) -> int:
        return kills * self.points_per_kill


class Season(TimeStampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, unique=True)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    scoring_rule = models.ForeignKey(ScoringRule, on_delete=models.PROTECT, related_name="seasons")
    tiebreakers = models.JSONField(
        default=default_tiebreakers, help_text=f"Ordered list from {TIEBREAKER_CHOICES}"
    )

    class Meta:
        ordering = ["-starts_on", "-id"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Season, self.name)
        super().save(*args, **kwargs)
        if self.is_active:  # one current season: the one the site shows by default
            Season.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)

    def clean(self) -> None:
        bad = [t for t in self.tiebreakers or [] if t not in TIEBREAKER_CHOICES]
        if bad:
            raise ValidationError({"tiebreakers": f"Unknown tiebreakers: {bad}"})


class Stage(TimeStampedModel):
    class Kind(models.TextChoices):
        GROUP = "GROUP", "Group stage"
        KNOCKOUT = "KNOCKOUT", "Knockout"
        FINAL = "FINAL", "Final"

    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="stages")
    name = models.CharField(max_length=80)
    order = models.PositiveIntegerField(default=1)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.GROUP)

    class Meta:
        ordering = ["season", "order"]
        unique_together = [("season", "name")]

    def __str__(self) -> str:
        return f"{self.season} / {self.name}"


class Team(TimeStampedModel):
    name = models.CharField(max_length=80, unique=True)
    tag = models.CharField(max_length=12, blank=True)
    slug = models.SlugField(max_length=90, unique=True)
    logo = models.FileField(upload_to="teams/logos/", blank=True)
    primary_color = models.CharField(max_length=7, blank=True, help_text="#RRGGBB")
    secondary_color = models.CharField(max_length=7, blank=True, help_text="#RRGGBB")
    socials = models.JSONField(default=dict, blank=True)
    is_league_member = models.BooleanField(default=True)
    plan = models.ForeignKey(
        "accounts.Plan",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="teams",
        help_text="League teams get the league_team plan automatically",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Team, self.name)
        if self.plan_id is None and self.is_league_member:
            from apps.accounts.models import Plan

            self.plan = Plan.objects.filter(code=Plan.LEAGUE_TEAM).first()
        super().save(*args, **kwargs)


class Group(TimeStampedModel):
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, related_name="groups")
    name = models.CharField(max_length=40)
    teams = models.ManyToManyField(Team, blank=True, related_name="league_groups")

    class Meta:
        ordering = ["stage", "name"]
        unique_together = [("stage", "name")]

    def __str__(self) -> str:
        return f"{self.stage} / {self.name}"


class MatchDay(TimeStampedModel):
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, related_name="match_days")
    group = models.ForeignKey(
        Group, on_delete=models.SET_NULL, null=True, blank=True, related_name="match_days"
    )
    number = models.PositiveIntegerField()
    date = models.DateField(null=True, blank=True)
    title = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["stage", "number"]
        unique_together = [("stage", "group", "number")]

    def __str__(self) -> str:
        return self.title or f"{self.stage} / Day {self.number}"

    @property
    def season(self) -> Season:
        return self.stage.season


class TeamAlias(TimeStampedModel):
    """An in-game team name as the logs spell it, mapped to a league team.

    ``season`` is optional: an alias without a season applies to every season.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="aliases")
    in_game_name = models.CharField(max_length=80)
    season = models.ForeignKey(
        Season, on_delete=models.CASCADE, null=True, blank=True, related_name="team_aliases"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["in_game_name", "season"], name="unique_alias_per_season"
            ),
            models.UniqueConstraint(
                fields=["in_game_name"],
                condition=models.Q(season__isnull=True),
                name="unique_global_alias",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.in_game_name} -> {self.team}"

    @classmethod
    def resolve(cls, in_game_name: str, season: Season | None) -> Team | None:
        aliases = cls.objects.select_related("team").filter(in_game_name=in_game_name)
        if season is not None:
            seasonal = aliases.filter(season=season).first()
            if seasonal:
                return seasonal.team
        general = aliases.filter(season__isnull=True).first()
        if general:
            return general.team
        return Team.objects.filter(name=in_game_name).first()


class Player(TimeStampedModel):
    """A Free Fire account, keyed by its permanent game UID."""

    game_uid = models.BigIntegerField(unique=True)
    current_name_raw = models.CharField(max_length=80)
    display_name = models.CharField(max_length=80)
    search_name = models.CharField(max_length=80, db_index=True)
    current_team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="players"
    )
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="player",
        help_text="The site account linked to this game UID",
    )
    country = models.CharField(max_length=2, blank=True)

    class Meta:
        ordering = ["display_name"]

    def __str__(self) -> str:
        return f"{self.display_name} ({self.game_uid})"


class RosterEntry(TimeStampedModel):
    """A player on a team for a season."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="roster_entries")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="roster_entries")
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="roster_entries")
    role = models.CharField(max_length=40, blank=True, help_text="IGL, rusher, sniper...")
    joined_on = models.DateField(null=True, blank=True)
    left_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["season", "team", "player__display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["player", "season"],
                condition=models.Q(left_on__isnull=True),
                name="one_active_roster_entry_per_season",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.player} - {self.team} ({self.season})"


class Match(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PROCESSING = "PROCESSING", "Processing"
        NEEDS_REVIEW = "NEEDS_REVIEW", "Needs review"
        PUBLISHED = "PUBLISHED", "Published"

    match_day = models.ForeignKey(MatchDay, on_delete=models.PROTECT, related_name="matches")
    number = models.PositiveIntegerField(help_text="Order within the match day")
    map = models.ForeignKey(
        "maps.Map", on_delete=models.SET_NULL, null=True, blank=True, related_name="matches"
    )
    game_match_id = models.BigIntegerField(unique=True, null=True, blank=True)
    game_map_id = models.IntegerField(null=True, blank=True)
    room_name = models.CharField(max_length=120, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    duration_s = models.FloatField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    safe_zones = models.JSONField(
        default=list, blank=True, help_text="Raw SafeZone files [{x, z, at}], reference only"
    )
    vod_url = models.URLField(blank=True)

    class Meta:
        ordering = ["match_day", "number"]
        unique_together = [("match_day", "number")]
        verbose_name_plural = "matches"

    def __str__(self) -> str:
        return f"{self.match_day} / Match {self.number}"

    @property
    def season(self) -> Season:
        return self.match_day.stage.season


def unique_slug(model: type[models.Model], text: str, max_length: int = 80) -> str:
    base = slugify(text, allow_unicode=False)[:max_length] or model._meta.model_name
    slug, n = base, 2
    while model.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug
