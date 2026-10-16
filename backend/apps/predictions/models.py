"""Virtual coins: a wallet per user and an append-only ledger of every coin movement.

Coins have no money value: they can't be bought, cashed out or sent to another user.

The ledger is the record of what happened; ``Wallet.balance`` is a stored copy kept in the
same database transaction as each entry (see ``services.post_entry``), so it can be read
and locked cheaply. ``check_wallets`` proves the two agree.
"""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="wallet"
    )
    balance = models.BigIntegerField(default=0, help_text="Whole coins; never below 0")
    entry_count = models.PositiveIntegerField(default=0, help_text="Ledger entries so far")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(balance__gte=0), name="predictions_wallet_balance_not_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} ({self.balance} coins)"


class LedgerEntry(models.Model):
    """One coin movement. Never edited or deleted; mistakes are fixed with a new entry."""

    class Kind(models.TextChoices):
        INITIAL = "INITIAL", "Starting coins"
        STAKE = "STAKE", "Stake"
        PAYOUT = "PAYOUT", "Winning payout"
        REFUND = "REFUND", "Refund (void)"
        CORRECTION = "CORRECTION", "Settlement correction"
        ADJUSTMENT = "ADJUSTMENT", "Staff adjustment"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="entries")
    seq = models.PositiveIntegerField(help_text="1, 2, 3... per wallet, in order")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    amount = models.BigIntegerField(help_text="Coins added (positive) or taken (negative)")
    balance_before = models.BigIntegerField()
    balance_after = models.BigIntegerField()
    idempotency_key = models.CharField(
        max_length=120, unique=True, help_text="The same operation can only happen once"
    )
    reason = models.CharField(max_length=300, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="The staff member who made an adjustment",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "ledger entries"
        constraints = [
            models.UniqueConstraint(fields=["wallet", "seq"], name="predictions_entry_seq"),
            models.CheckConstraint(
                condition=Q(balance_after=F("balance_before") + F("amount")),
                name="predictions_entry_adds_up",
            ),
            models.CheckConstraint(
                condition=Q(balance_after__gte=0), name="predictions_entry_not_negative"
            ),
            models.CheckConstraint(condition=~Q(amount=0), name="predictions_entry_not_zero"),
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.amount:+d} -> {self.balance_after}"
