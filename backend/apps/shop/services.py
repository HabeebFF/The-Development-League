"""Buying, equipping, refunding and gifting card designs.

Buying locks the design row first (so limited copies can't be oversold when many people buy
at once), then takes the coins through ``post_entry`` (which locks the wallet and refuses a
balance below 0). Everything is one transaction: if the coins can't be taken, no copy exists.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.predictions.services import CoinError, Kind, can_play, post_entry, wallet_for

from .models import CardDesign, Equipped, OwnedDesign


class ShopError(Exception):
    """A refused shop action; ``str()`` is safe to show the user."""


def live_copies(design: CardDesign):
    return design.owners.filter(refunded_at__isnull=True)


def available(design: CardDesign, now=None) -> bool:
    now = now or timezone.now()
    return design.on_sale and (design.sale_ends is None or design.sale_ends > now)


def _next_copy(design: CardDesign) -> int:
    """The lowest copy number no live copy holds (a refunded number is given out again)."""
    taken = set(live_copies(design).values_list("copy_number", flat=True))
    n = 1
    while n in taken:
        n += 1
    return n


def buy(user, design_id: int) -> OwnedDesign:
    if not can_play(user):
        raise ShopError("League staff can't buy designs.")
    wallet = wallet_for(user)
    with transaction.atomic():
        design = CardDesign.objects.select_for_update().filter(pk=design_id).first()
        if design is None or not available(design):
            raise ShopError("This design isn't on sale.")
        if live_copies(design).filter(user=user).exists():
            raise ShopError("You already own this design.")
        if design.copies is not None and live_copies(design).count() >= design.copies:
            raise ShopError("Sold out: every copy of this design has been bought.")
        owned = OwnedDesign.objects.create(
            user=user, design=design, copy_number=_next_copy(design), price_paid=design.price
        )
        if design.price:
            try:
                entry, _ = post_entry(
                    wallet,
                    Kind.PURCHASE,
                    -design.price,
                    f"shop:{owned.pk}",
                    reason=f"Bought {design.name}",
                )
            except CoinError as exc:
                raise ShopError(str(exc)) from exc
            owned.entry = entry
            owned.save(update_fields=["entry"])
    return owned


def equip(user, design_id: int | None) -> Equipped:
    """Put an owned design on the user's cards (``None`` goes back to Default)."""
    design = None
    if design_id is not None:
        owned = (
            OwnedDesign.objects.filter(user=user, design_id=design_id, refunded_at__isnull=True)
            .select_related("design")
            .first()
        )
        if owned is None:
            raise ShopError("You don't own this design.")
        design = owned.design
    eq, _ = Equipped.objects.get_or_create(user=user)
    eq.design = design
    eq.save(update_fields=["design", "updated_at"])
    return eq


def unequip_if(user_id: int, design_id: int) -> None:
    Equipped.objects.filter(user_id=user_id, design_id=design_id).update(design=None)


def refund(owned_id, actor) -> OwnedDesign:
    """Staff: give the coins back and take the design away (off their cards too)."""
    with transaction.atomic():
        owned = (
            OwnedDesign.objects.select_for_update()
            .select_related("design")
            .filter(pk=owned_id)
            .first()
        )
        if owned is None:
            raise ShopError("No such purchase.")
        if owned.refunded_at is not None:
            raise ShopError("This purchase was already refunded.")
        if owned.price_paid:
            post_entry(
                wallet_for(owned.user),
                Kind.SHOP_REFUND,
                owned.price_paid,
                f"shop-refund:{owned.pk}",
                reason=f"Refund for {owned.design.name}",
                actor=actor,
            )
        owned.refunded_at = timezone.now()
        owned.refunded_by = actor
        owned.save(update_fields=["refunded_at", "refunded_by"])
        unequip_if(owned.user_id, owned.design_id)
    return owned


def gift(user, design_id: int, actor, note: str = "") -> OwnedDesign:
    """Staff: give a design for free (for example to an award winner). Limited copies count."""
    with transaction.atomic():
        design = CardDesign.objects.select_for_update().filter(pk=design_id).first()
        if design is None:
            raise ShopError("No such design.")
        if live_copies(design).filter(user=user).exists():
            raise ShopError("They already own this design.")
        if design.copies is not None and live_copies(design).count() >= design.copies:
            raise ShopError("Sold out: every copy of this design has gone.")
        return OwnedDesign.objects.create(
            user=user,
            design=design,
            copy_number=_next_copy(design),
            price_paid=0,
            gifted_by=actor,
            gift_note=note[:200],
        )


# -- what cards show ---------------------------------------------------------------------------


def design_data(design: CardDesign | None, copy_number: int | None = None) -> dict | None:
    if design is None:
        return None
    return {
        "id": design.pk,
        "slug": design.slug,
        "name": design.name,
        "rarity": design.rarity,
        "parts": design.parts,
        "copy_number": copy_number if design.copies is not None else None,
        "copies": design.copies,
    }


def equipped_designs(user_ids=None) -> dict[int, dict]:
    """``{user_id: design data}`` for users with a design on (all users if ``None``)."""
    qs = Equipped.objects.filter(design__isnull=False).select_related("design")
    if user_ids is not None:
        qs = qs.filter(user_id__in=list(user_ids))
    rows = list(qs)
    copies = {
        (u, d): n
        for u, d, n in OwnedDesign.objects.filter(
            refunded_at__isnull=True, user_id__in=[e.user_id for e in rows]
        ).values_list("user_id", "design_id", "copy_number")
    }
    out = {}
    for e in rows:
        key = (e.user_id, e.design_id)
        if key in copies:  # still owned (a refund also unequips, this is belt and braces)
            out[e.user_id] = design_data(e.design, copies[key])
    return out


def design_for_player(player, request=None) -> dict | None:
    """The design a linked player has on, for their weekly card. Cached on the request so a
    gallery of 100 cards makes one query."""
    if not player.user_id:
        return None
    if request is None:
        return equipped_designs([player.user_id]).get(player.user_id)
    cache = getattr(request, "_shop_designs", None)
    if cache is None:
        cache = equipped_designs()
        request._shop_designs = cache
    return cache.get(player.user_id)
