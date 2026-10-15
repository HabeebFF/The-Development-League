"""The only code that changes coin balances.

Every movement goes through ``post_entry``: it locks the wallet row, refuses a second use of
the same idempotency key, refuses a balance below 0, and writes the ledger entry and the new
balance in one transaction. Anything that fails rolls the whole operation back.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Sum

from .models import LedgerEntry, Wallet

Kind = LedgerEntry.Kind


class CoinError(Exception):
    """A coin movement that was refused; ``str()`` is safe to show the user."""


class NotEnoughCoins(CoinError):
    pass


class KeyReused(CoinError):
    """The idempotency key was already used for a different movement."""


def initial_coins() -> int:
    return settings.PREDICTIONS_INITIAL_COINS


def can_play(user) -> bool:
    """Staff set odds and settle results, so they can't play."""
    return bool(user and user.is_authenticated and not user.is_league_staff)


def post_entry(
    wallet: Wallet | int,
    kind: str,
    amount: int,
    key: str,
    *,
    reason: str = "",
    actor=None,
) -> tuple[LedgerEntry, bool]:
    """Add ``amount`` coins (negative to take) once per ``key``.

    Returns ``(entry, created)``. Repeating a call with the same key returns the first entry
    and changes nothing, so retries are safe.
    """
    if not isinstance(amount, int) or isinstance(amount, bool) or amount == 0:
        raise CoinError("The amount must be a whole number of coins, not 0.")
    wallet_id = wallet.pk if isinstance(wallet, Wallet) else wallet
    with transaction.atomic():
        locked = Wallet.objects.select_for_update().get(pk=wallet_id)
        existing = LedgerEntry.objects.filter(idempotency_key=key).first()
        if existing is not None:
            if (existing.wallet_id, existing.kind, existing.amount) != (locked.pk, kind, amount):
                raise KeyReused("This operation was already used for something else.")
            return existing, False
        after = locked.balance + amount
        if after < 0:
            raise NotEnoughCoins(f"Not enough coins: you have {locked.balance}.")
        entry = LedgerEntry.objects.create(
            wallet=locked,
            seq=locked.entry_count + 1,
            kind=kind,
            amount=amount,
            balance_before=locked.balance,
            balance_after=after,
            idempotency_key=key,
            reason=reason,
            actor=actor,
        )
        locked.balance = after
        locked.entry_count += 1
        locked.save(update_fields=["balance", "entry_count", "updated_at"])
    if isinstance(wallet, Wallet):
        wallet.balance, wallet.entry_count = locked.balance, locked.entry_count
    return entry, True


def wallet_for(user) -> Wallet:
    """The user's wallet, created with the starting coins the first time.

    The wallet and its INITIAL entry are written together, so a wallet never exists without
    its starting coins and the starting coins can never be given twice (the user is unique
    on the wallet and ``initial:<wallet>`` is unique in the ledger).
    """
    wallet = Wallet.objects.filter(user=user).first()
    if wallet is not None:
        return wallet
    try:
        with transaction.atomic():
            wallet = Wallet.objects.create(user=user)
            post_entry(wallet, Kind.INITIAL, initial_coins(), f"initial:{wallet.pk}")
    except IntegrityError:
        # Another request created it at the same moment; use that one.
        return Wallet.objects.get(user=user)
    return wallet


@dataclass
class WalletProblem:
    wallet_id: int
    problem: str


def check_wallet(wallet: Wallet) -> list[str]:
    """Why this wallet's balance and ledger disagree (empty when they agree)."""
    problems = []
    total = wallet.entries.aggregate(total=Sum("amount"))["total"] or 0
    if total != wallet.balance:
        problems.append(f"balance {wallet.balance} but ledger adds up to {total}")
    entries = list(wallet.entries.order_by("seq"))
    if len(entries) != wallet.entry_count:
        problems.append(f"{len(entries)} entries but the wallet counts {wallet.entry_count}")
    running = 0
    for n, entry in enumerate(entries, start=1):
        if entry.seq != n:
            problems.append(f"entry {entry.pk} is number {entry.seq}, expected {n}")
        if entry.balance_before != running:
            problems.append(
                f"entry {entry.pk} starts at {entry.balance_before}, expected {running}"
            )
        running = entry.balance_after
    initials = sum(1 for e in entries if e.kind == Kind.INITIAL)
    if initials != 1:
        problems.append(f"{initials} starting-coin entries (should be 1)")
    return problems


def check_wallets() -> list[WalletProblem]:
    out = []
    for wallet in Wallet.objects.order_by("pk").iterator():
        out.extend(WalletProblem(wallet.pk, p) for p in check_wallet(wallet))
    return out
