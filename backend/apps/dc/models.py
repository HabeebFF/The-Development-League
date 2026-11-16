"""DC for players: coins earned by playing (see design/DC-FOR-PLAYERS.md)."""

from django.conf import settings
from django.db import models


class DcSettings(models.Model):
    """Staff settings for DC earned by playing (one row)."""

    rewards_enabled = models.BooleanField(default=True, help_text="Pay DC after each upload")
    per_kill = models.PositiveIntegerField(default=100)
    booyah = models.PositiveIntegerField(default=1000, help_text="Each player on the winning team")
    mvp = models.PositiveIntegerField(default=500, help_text="The match MVP")
    played = models.PositiveIntegerField(default=50, help_text="Every player in the match")
    start_date = models.DateField(
        null=True, blank=True, help_text="Matches from this day (Lagos) earn DC"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "DC settings"
        verbose_name_plural = "DC settings"

    @classmethod
    def get(cls) -> "DcSettings":
        conf, created = cls.objects.get_or_create(pk=1)
        if conf.start_date is None:
            from apps.predictions.services import lagos_today

            conf.start_date = lagos_today()
            conf.save(update_fields=["start_date", "updated_at"])
        return conf


class MatchReward(models.Model):
    """What one player earned in one match. ``amount`` is what they're owed now; ``paid`` is
    what has been settled with their wallet (paid, or taken back). A difference is DC still
    to move: waiting for an unlinked player, or a correction after a re-upload."""

    match = models.ForeignKey("league.Match", on_delete=models.CASCADE, related_name="dc_rewards")
    player = models.ForeignKey("league.Player", on_delete=models.CASCADE, related_name="dc_rewards")
    team = models.ForeignKey(
        "league.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    kills = models.PositiveSmallIntegerField(default=0)
    booyah = models.BooleanField(default=False)
    mvp = models.BooleanField(default=False)
    amount = models.PositiveIntegerField(default=0)
    paid = models.IntegerField(default=0, help_text="Settled with a wallet so far")
    shortfall = models.PositiveIntegerField(
        default=0, help_text="DC that couldn't be taken back (the wallet had too little)"
    )
    paid_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    moves = models.PositiveIntegerField(default=0, help_text="Ledger entries so far")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["match", "player"], name="dc_reward_one_per_match")
        ]
        indexes = [models.Index(fields=["player", "match"])]

    def __str__(self) -> str:
        return f"{self.player_id} in match {self.match_id}: {self.amount} DC"

    @property
    def waiting(self) -> int:
        return self.amount - self.paid

    def breakdown(self) -> str:
        parts = []
        if self.kills:
            parts.append(f"{self.kills} kill{'s' if self.kills != 1 else ''}")
        if self.booyah:
            parts.append("Booyah")
        if self.mvp:
            parts.append("MVP")
        return ", ".join(parts) or "played"
