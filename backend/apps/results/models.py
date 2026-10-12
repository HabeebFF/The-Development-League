"""What happened in a match: results per team and player, events and zone phases.

All positions are game world coordinates (x, y = height, z).
"""

from django.db import models

from common.models import TimeStampedModel


class TeamMatchResult(TimeStampedModel):
    match = models.ForeignKey("league.Match", on_delete=models.CASCADE, related_name="team_results")
    team = models.ForeignKey("league.Team", on_delete=models.PROTECT, related_name="match_results")
    in_game_name = models.CharField(max_length=80)
    slot = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="entity_id >> 24 in this match (not the log TeamID)"
    )
    log_team_id = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="TeamID from OnTeamScoreInited"
    )
    placement = models.PositiveSmallIntegerField()
    kills = models.PositiveSmallIntegerField()
    placement_points = models.IntegerField()
    kill_points = models.IntegerField()
    total_points = models.IntegerField()
    reported_rank_score = models.IntegerField(null=True, blank=True)
    reported_total_score = models.IntegerField(null=True, blank=True)
    eliminated_at_s = models.FloatField(null=True, blank=True, help_text="Game seconds")

    class Meta:
        ordering = ["match", "placement"]
        unique_together = [("match", "team")]

    def __str__(self) -> str:
        return f"{self.match}: #{self.placement} {self.team}"

    @property
    def is_booyah(self) -> bool:
        return self.placement == 1


class PlayerMatchResult(TimeStampedModel):
    match = models.ForeignKey(
        "league.Match", on_delete=models.CASCADE, related_name="player_results"
    )
    player = models.ForeignKey(
        "league.Player", on_delete=models.PROTECT, related_name="match_results"
    )
    team = models.ForeignKey(
        "league.Team", on_delete=models.PROTECT, related_name="player_match_results"
    )
    raw_name = models.CharField(max_length=80)
    display_name = models.CharField(max_length=80)
    entity_id = models.BigIntegerField(null=True, blank=True)
    kills = models.PositiveSmallIntegerField(default=0)
    knocks = models.PositiveSmallIntegerField(null=True, blank=True)
    headshot_knocks = models.PositiveSmallIntegerField(null=True, blank=True)
    deaths = models.PositiveSmallIntegerField(null=True, blank=True)
    respawns = models.PositiveSmallIntegerField(null=True, blank=True)
    is_mvp = models.BooleanField(default=False)

    class Meta:
        ordering = ["match", "team", "-kills"]
        unique_together = [("match", "player")]

    def __str__(self) -> str:
        return f"{self.match}: {self.display_name}"


class MatchEvent(models.Model):
    class Kind(models.TextChoices):
        KILL = "KILL", "Kill"
        KNOCK = "KNOCK", "Knock"
        DEATH = "DEATH", "Death (with position)"
        RESPAWN = "RESPAWN", "Respawn drop"
        TELEPORT = "TELEPORT", "Teleport"
        TEAM_ELIMINATED = "TEAM_ELIMINATED", "Team eliminated"

    class Source(models.TextChoices):
        DEBUGGER = "DEBUGGER", "Debugger log"
        REPLAY_INFO = "REPLAY_INFO", "ReplayInfo"

    match = models.ForeignKey("league.Match", on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    source = models.CharField(max_length=12, choices=Source.choices)
    game_time_s = models.FloatField(null=True, blank=True, help_text="Seconds from match start")
    wall_time = models.DateTimeField(null=True, blank=True)
    actor_entity = models.BigIntegerField(null=True, blank=True)
    target_entity = models.BigIntegerField(null=True, blank=True)
    actor_player = models.ForeignKey(
        "league.Player", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    target_player = models.ForeignKey(
        "league.Player", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    actor_team = models.ForeignKey(
        "league.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    target_team = models.ForeignKey(
        "league.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    headshot = models.BooleanField(null=True, blank=True)
    weapon_id = models.IntegerField(null=True, blank=True)
    x = models.FloatField(null=True, blank=True)
    y = models.FloatField(null=True, blank=True)
    z = models.FloatField(null=True, blank=True)
    tx = models.FloatField(null=True, blank=True)
    ty = models.FloatField(null=True, blank=True)
    tz = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["match", "game_time_s", "id"]
        indexes = [
            models.Index(fields=["match", "kind"]),
            models.Index(fields=["match", "game_time_s"]),
        ]

    def __str__(self) -> str:
        return f"{self.match}: {self.kind} @ {self.game_time_s}"


class ZonePhase(models.Model):
    class State(models.TextChoices):
        STABLE = "STABLE", "Stable"
        PRE_SHRINK = "PRE_SHRINK", "Pre-shrink"
        SHRINK = "SHRINK", "Shrink"

    match = models.ForeignKey("league.Match", on_delete=models.CASCADE, related_name="zones")
    stage_index = models.PositiveSmallIntegerField()
    state = models.CharField(max_length=16)
    game_time_s = models.FloatField(null=True, blank=True)
    wall_time = models.DateTimeField(null=True, blank=True)
    outer_x = models.FloatField()
    outer_z = models.FloatField()
    outer_radius = models.FloatField(
        null=True, blank=True, help_text="Not logged; the previous stage's inner radius"
    )
    inner_x = models.FloatField()
    inner_z = models.FloatField()
    inner_radius = models.FloatField()

    class Meta:
        ordering = ["match", "stage_index", "game_time_s"]
        unique_together = [("match", "stage_index", "state")]

    def __str__(self) -> str:
        return f"{self.match}: zone {self.stage_index} {self.state}"


class StandingRow(TimeStampedModel):
    """One team's line in a standings table (materialised; rebuilt, never edited).

    A table is a *scope*: the whole season, one stage, one group or one match day.
    ``scope`` is a string key ("season", "stage:3", "group:5", "day:7") so each table is
    unique per team without relying on NULL comparisons.
    """

    season = models.ForeignKey("league.Season", on_delete=models.CASCADE, related_name="standings")
    scope = models.CharField(max_length=24)
    stage = models.ForeignKey(
        "league.Stage", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    group = models.ForeignKey(
        "league.Group", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    match_day = models.ForeignKey(
        "league.MatchDay", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    team = models.ForeignKey("league.Team", on_delete=models.CASCADE, related_name="standings")
    rank = models.PositiveSmallIntegerField()
    matches_played = models.PositiveSmallIntegerField(default=0)
    booyahs = models.PositiveSmallIntegerField(default=0)
    kills = models.PositiveIntegerField(default=0)
    placement_points = models.IntegerField(default=0)
    kill_points = models.IntegerField(default=0)
    total_points = models.IntegerField(default=0)
    avg_placement = models.FloatField(null=True, blank=True)
    last_match_points = models.IntegerField(null=True, blank=True)
    form = models.JSONField(
        default=list, blank=True, help_text="Placements in the last five matches, oldest first"
    )

    class Meta:
        ordering = ["season", "scope", "rank", "team__name"]
        constraints = [
            models.UniqueConstraint(fields=["season", "scope", "team"], name="unique_standing")
        ]
        indexes = [models.Index(fields=["season", "scope", "rank"])]

    def __str__(self) -> str:
        return f"{self.season} [{self.scope}] #{self.rank} {self.team}"


class PlayerCard(models.Model):
    """A player's card for one week (Monday to Sunday): rebuilt from the four weeks up to
    and including it (see ``apps.results.cards``)."""

    player = models.ForeignKey("league.Player", on_delete=models.CASCADE, related_name="cards")
    week = models.DateField(help_text="The Monday the week starts")
    team = models.ForeignKey(
        "league.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    role = models.CharField(max_length=12)
    role_suggested = models.BooleanField(
        default=False, help_text="Staff haven't set a role: this is the site's suggestion"
    )
    suggested_role = models.CharField(max_length=12, blank=True)
    overall = models.PositiveSmallIntegerField()
    overall_change = models.SmallIntegerField(null=True, blank=True)
    stats = models.JSONField(
        default=list, help_text="[{key, rating, change, stale, value, detail}] in card order"
    )
    matches = models.PositiveSmallIntegerField(help_text="Matches in the 4-week window")
    week_matches = models.PositiveSmallIntegerField(default=0)
    stale = models.BooleanField(
        default=False, help_text="Too few matches: last week's numbers carried over"
    )
    totw = models.JSONField(default=list, blank=True, help_text="Awards won this week")
    special = models.CharField(
        max_length=12, blank=True, help_text="rising_star or icon (see cards.mark_specials)"
    )
    rise = models.SmallIntegerField(
        null=True, blank=True, help_text="A Rising Star's jump in overall since their last card"
    )
    streak = models.PositiveSmallIntegerField(
        default=0, help_text="Back-to-back weeks at the Icon rating, this one included"
    )
    rules = models.CharField(max_length=20)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-week", "-overall"]
        constraints = [
            models.UniqueConstraint(fields=["player", "week"], name="one_card_per_player_week")
        ]
        indexes = [models.Index(fields=["week", "overall"])]

    def __str__(self) -> str:
        return f"{self.player} {self.week}: {self.overall} {self.role}"


class CardWeights(models.Model):
    """Staff's weights for each role's overall rating (one row; empty uses the defaults)."""

    weights = models.JSONField(default=dict, blank=True, help_text="{role: {stat: weight}}")
    rising_min = models.PositiveSmallIntegerField(
        default=10, help_text="Rise in overall since the last card that makes a Rising Star"
    )
    icon_min = models.PositiveSmallIntegerField(default=95, help_text="Overall an Icon keeps")
    icon_weeks = models.PositiveSmallIntegerField(
        default=4, help_text="Back-to-back weeks at icon_min that make an Icon"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "card weights"

    def __str__(self) -> str:
        return "Card weights"
