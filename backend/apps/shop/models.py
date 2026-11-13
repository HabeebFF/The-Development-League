"""The card shop: card designs bought with DC (virtual coins, no money value) and equipped.

A design only changes how a card looks (frame, colours, effect), never the numbers on it.
Coins move only through ``apps.predictions.services.post_entry`` (kinds PURCHASE and
SHOP_REFUND), so every purchase and refund is in the wallet's append-only ledger.
"""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class CardDesign(models.Model):
    class Rarity(models.TextChoices):
        COMMON = "COMMON", "Common"
        RARE = "RARE", "Rare"
        EPIC = "EPIC", "Epic"
        LEGENDARY = "LEGENDARY", "Legendary"
        VINTAGE = "VINTAGE", "Vintage"
        DIAMOND = "DIAMOND", "Diamond"

    slug = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=60)
    rarity = models.CharField(max_length=10, choices=Rarity.choices, default=Rarity.COMMON)
    price = models.PositiveIntegerField(help_text="DC")
    parts = models.JSONField(default=dict, help_text="palette, pattern, effect (see looks.py)")
    copies = models.PositiveIntegerField(
        null=True, blank=True, help_text="Limited to this many copies; empty = unlimited"
    )
    sale_ends = models.DateTimeField(null=True, blank=True, help_text="Off sale after this")
    on_sale = models.BooleanField(default=True, help_text="Untick to hide it from the shop")
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "price", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.price} DC)"


class OwnedDesign(models.Model):
    """One user's copy of a design: bought (``entry`` is the PURCHASE) or gifted by staff.

    A refund keeps the row (``refunded_at`` set) so the history stays; the user can buy the
    design again later."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_designs"
    )
    design = models.ForeignKey(CardDesign, on_delete=models.PROTECT, related_name="owners")
    copy_number = models.PositiveIntegerField(help_text="1, 2, 3... per design")
    price_paid = models.PositiveIntegerField(default=0)
    entry = models.OneToOneField(
        "predictions.LedgerEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    gifted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    gift_note = models.CharField(max_length=200, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    refunded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "design"],
                condition=Q(refunded_at__isnull=True),
                name="shop_own_design_once",
            ),
            models.UniqueConstraint(
                fields=["design", "copy_number"],
                condition=Q(refunded_at__isnull=True),
                name="shop_copy_number",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} owns {self.design} #{self.copy_number}"


class Equipped(models.Model):
    """The design a user has on their cards (FUT card if they're a linked player, and their
    fan card). No row, or ``design`` empty, means the plain Default look."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="equipped"
    )
    design = models.ForeignKey(
        CardDesign, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    favourite_team = models.ForeignKey(
        "league.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user}: {self.design or 'Default'}"
