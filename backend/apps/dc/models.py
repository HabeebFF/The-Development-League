"""DC for players: coins earned by playing (see design/DC-FOR-PLAYERS.md)."""

from django.conf import settings
from django.db import models


def default_rank_steps() -> list:
    """DC ranks by DC earned (Habeeb approved 2026-11-16)."""
    return [
        {"key": "bronze", "name": "Bronze", "min": 5_000},
        {"key": "silver", "name": "Silver", "min": 25_000},
        {"key": "gold", "name": "Gold", "min": 100_000},
        {"key": "elite", "name": "Elite", "min": 500_000},
        {"key": "legend", "name": "Legend", "min": 2_000_000},
    ]


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
    rank_steps = models.JSONField(
        default=default_rank_steps, help_text="DC ranks: name and the DC earned to reach it"
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


class Spotlight(models.Model):
    """DC King of a month: the player who earned the most DC in it. Shown on the home page and
    in broadcast labels for the whole month after."""

    month = models.DateField(unique=True, help_text="First day of the month they won")
    player = models.ForeignKey("league.Player", on_delete=models.CASCADE, related_name="+")
    earned = models.BigIntegerField()
    from_matches = models.BigIntegerField(default=0, help_text="Of which from matches")
    hidden = models.BooleanField(default=False, help_text="Staff hid it from the site")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-month"]

    def __str__(self) -> str:
        return f"DC King {self.month:%B %Y}: {self.player_id}"


class Perk(models.Model):
    """Something DC buys that changes how a player or team is seen, never how they play."""

    class Key(models.TextChoices):
        BANNER = "BANNER", "Team banner"
        THEME = "THEME", "Team colours"
        SHOUTOUT = "SHOUTOUT", "Home page shoutout"
        PIN = "PIN", "Pinned moment"
        NAME_COLOUR = "NAME_COLOUR", "Name colour"

    key = models.CharField(max_length=12, choices=Key.choices, unique=True)
    price = models.PositiveIntegerField(help_text="DC")
    days = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="How long it lasts; empty = until replaced"
    )
    for_team = models.BooleanField(default=False, help_text="Paid from the team pot")
    enabled = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self) -> str:
        return self.get_key_display()


class TeamPot(models.Model):
    """DC a team's players put together for team perks. Can only be spent, never taken out."""

    team = models.OneToOneField("league.Team", on_delete=models.CASCADE, related_name="dc_pot")
    balance = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class PotEntry(models.Model):
    """One movement in a team pot: a player chipping in (+) or a perk bought (-)."""

    pot = models.ForeignKey(TeamPot, on_delete=models.CASCADE, related_name="entries")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    amount = models.BigIntegerField()
    balance_after = models.BigIntegerField()
    note = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]


class PerkPurchase(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Waiting for staff"
        ACTIVE = "ACTIVE", "Active"
        REJECTED = "REJECTED", "Turned down (refunded)"
        REMOVED = "REMOVED", "Removed by staff"
        REPLACED = "REPLACED", "Replaced by a newer one"

    perk = models.ForeignKey(Perk, on_delete=models.PROTECT, related_name="purchases")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="perk_purchases"
    )
    player = models.ForeignKey(
        "league.Player", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    team = models.ForeignKey(
        "league.Team", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    price_paid = models.PositiveIntegerField()
    from_pot = models.BooleanField(default=False)
    status = models.CharField(max_length=8, choices=Status.choices)
    data = models.JSONField(default=dict, blank=True, help_text="Colours, text, palette, moment")
    image = models.FileField(upload_to="teams/banners/", blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    review_note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["perk", "status"])]
