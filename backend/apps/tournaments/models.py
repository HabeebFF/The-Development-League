"""Tournaments: a cup with its own standings, a prize table (cash shown, DC paid) and payouts.

A tournament owns its own season (seasons > stages > match days), so its matches are uploaded
with the normal upload and kept out of the scrim standings. Cash is only shown: staff pay it
outside the site. DC is play money, paid to the winners' wallets when staff confirm.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from common.models import TimeStampedModel

# Prize rows: "place:1" (one place), "place:5-8" (each place in a range), "mvp",
# "top_kills" and "best_igl" (players). Cash in naira (display only), DC paid on confirm.
DEFAULT_PRIZES = [
    {"key": "place:1", "label": "1st", "cash": 40000, "dc": 300000},
    {"key": "place:2", "label": "2nd", "cash": 25000, "dc": 200000},
    {"key": "place:3", "label": "3rd", "cash": 15000, "dc": 125000},
    {"key": "place:4", "label": "4th", "cash": 8000, "dc": 75000},
    {"key": "place:5-8", "label": "5th to 8th", "cash": 0, "dc": 25000},
    {"key": "mvp", "label": "MVP", "cash": 7000, "dc": 100000},
    {"key": "top_kills", "label": "Most kills", "cash": 5000, "dc": 50000},
    {"key": "best_igl", "label": "Best IGL", "cash": 0, "dc": 50000},
]


def default_prizes() -> list[dict]:
    return [dict(p) for p in DEFAULT_PRIZES]


class Tournament(TimeStampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, unique=True)
    season = models.OneToOneField(
        "league.Season", on_delete=models.PROTECT, related_name="tournament"
    )
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    keyword = models.CharField(
        max_length=40,
        blank=True,
        help_text='Room names with this word ("CUP") go to the tournament on the upload page',
    )
    format_note = models.CharField(
        max_length=300, blank=True, help_text="e.g. 2 days, 6 maps each day, 10PM"
    )
    planned_matches = models.PositiveSmallIntegerField(
        default=12, help_text="Matches in all; prizes can be confirmed once they're all in"
    )
    teams = models.ManyToManyField("league.Team", blank=True, related_name="tournaments")
    prizes = models.JSONField(default=default_prizes)
    best_igl = models.ForeignKey(
        "league.Player", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    cash_paid = models.JSONField(
        default=list, blank=True, help_text="Prize keys whose cash staff have paid"
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-starts_on", "-id"]

    def __str__(self) -> str:
        return self.name


class PrizePayout(TimeStampedModel):
    """One player's share of one prize. Paid to their wallet at once, or held until the
    player has a site account (paid when their game UID is linked)."""

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="payouts")
    prize_key = models.CharField(max_length=20)
    label = models.CharField(max_length=60)
    player = models.ForeignKey("league.Player", on_delete=models.PROTECT, related_name="prizes")
    team = models.ForeignKey(
        "league.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    amount = models.PositiveIntegerField()
    paid_at = models.DateTimeField(null=True, blank=True)
    paid_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["tournament", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["tournament", "prize_key", "player"], name="one_share_per_prize"
            )
        ]

    def __str__(self) -> str:
        return f"{self.label}: {self.player} {self.amount} DC"
