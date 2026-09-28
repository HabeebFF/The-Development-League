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
