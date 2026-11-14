"""Buying, equipping, refunding and gifting card designs.

Buying locks the design row first (so limited copies can't be oversold when many people buy
at once), then takes the coins through ``post_entry`` (which locks the wallet and refuses a
balance below 0). Everything is one transaction: if the coins can't be taken, no copy exists.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q
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


def linked_player(user):
    """The league player this account is linked to (their FUT card), or ``None``."""
    from apps.league.models import Player

    if not (user and user.is_authenticated):
        return None
    return Player.objects.filter(user=user).first()


def buy(user, design_id: int) -> OwnedDesign:
    if not can_play(user):
        raise ShopError("League staff can't buy designs.")
    wallet = wallet_for(user)
    with transaction.atomic():
        design = CardDesign.objects.select_for_update().filter(pk=design_id).first()
        if design is None or not available(design):
            raise ShopError("This design isn't on sale.")
        if design.unlock:
            raise ShopError("This one can't be bought: players earn it at a milestone.")
        if design.players_only and linked_player(user) is None:
            raise ShopError("Only league players can buy from the Player shop.")
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


# Which ``Equipped`` field each kind of item goes in (number and flag are set by hand).
SLOTS = {
    CardDesign.Kind.FRAME: "design",
    CardDesign.Kind.TITLE: "title",
    CardDesign.Kind.GLOW: "glow",
}


def _owned(user, design_id: int) -> OwnedDesign:
    owned = (
        OwnedDesign.objects.filter(user=user, design_id=design_id, refunded_at__isnull=True)
        .select_related("design")
        .first()
    )
    if owned is None:
        raise ShopError("You don't own this design.")
    return owned


def equip(user, design_id: int | None, kind: str = CardDesign.Kind.FRAME) -> Equipped:
    """Put an owned item on the user's cards: a design (frame), a card title or a rating
    glow. ``None`` takes that kind off (a frame goes back to Default)."""
    if kind not in SLOTS:
        raise ShopError("That can't be equipped.")
    item = None
    if design_id is not None:
        item = _owned(user, design_id).design
        if item.kind != kind:
            raise ShopError("That item doesn't go there.")
        if item.players_only and linked_player(user) is None:
            raise ShopError("Player shop items only go on a league player's card.")
    slot = SLOTS[kind]
    eq, _ = Equipped.objects.get_or_create(user=user)
    setattr(eq, slot, item)
    eq.save(update_fields=[slot, "updated_at"])
    return eq


def equip_any(user, design: CardDesign) -> None:
    """Put a just-bought item on, whatever its kind (number and flag need a number first)."""
    if design.kind in SLOTS:
        equip(user, design.pk, design.kind)


def owns_number(user) -> bool:
    return OwnedDesign.objects.filter(
        user=user, refunded_at__isnull=True, design__kind=CardDesign.Kind.NUMBER
    ).exists()


def set_number(user, number: int | None, flag: str) -> Equipped:
    """A player's shirt number (0 to 99, or ``None``) and flag (two-letter country code)."""
    if not owns_number(user):
        raise ShopError("Buy Number and flag in the Player shop first.")
    if linked_player(user) is None:
        raise ShopError("Only league players have a number on their card.")
    if number is not None and not (0 <= number <= 99):
        raise ShopError("Pick a number from 0 to 99.")
    flag = (flag or "").strip().upper()
    if flag and not (len(flag) == 2 and flag.isalpha()):
        raise ShopError("Use a two-letter country code, like NG.")
    eq, _ = Equipped.objects.get_or_create(user=user)
    eq.shirt_number = number
    eq.flag = flag
    eq.save(update_fields=["shirt_number", "flag", "updated_at"])
    return eq


def unequip_if(user_id: int, design_id: int) -> None:
    """Take an item off whatever slot holds it (after a refund)."""
    for slot in SLOTS.values():
        Equipped.objects.filter(user_id=user_id, **{f"{slot}_id": design_id}).update(**{slot: None})
    if not OwnedDesign.objects.filter(
        user_id=user_id, refunded_at__isnull=True, design__kind=CardDesign.Kind.NUMBER
    ).exists():
        Equipped.objects.filter(user_id=user_id).update(shirt_number=None, flag="")


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
        if design.players_only and linked_player(user) is None:
            raise ShopError("Player shop items can only go to a league player's account.")
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


def extras_data(eq: Equipped) -> dict | None:
    """Player shop extras on a card: title, rating glow, shirt number and flag."""
    title, glow = eq.title, eq.glow
    out = {
        "title": title.name if title else None,
        "title_palette": title.parts.get("palette") if title else None,
        "glow": glow.parts.get("palette") if glow else None,
        "glow_effect": glow.parts.get("effect") if glow else None,
        "number": eq.shirt_number,
        "flag": eq.flag or None,
    }
    return out if any(v is not None for v in out.values()) else None


def player_extras(user_ids=None) -> dict[int, dict]:
    """``{user_id: extras}`` for users with any player shop extra on."""
    qs = Equipped.objects.select_related("title", "glow").filter(
        Q(title__isnull=False) | Q(glow__isnull=False) | Q(shirt_number__isnull=False) | ~Q(flag="")
    )
    if user_ids is not None:
        qs = qs.filter(user_id__in=list(user_ids))
    out = {}
    for eq in qs:
        data = extras_data(eq)
        if data:
            out[eq.user_id] = data
    return out


def extras_for_player(player, request=None) -> dict | None:
    """The extras on a linked player's weekly card, cached on the request like designs."""
    if not player.user_id:
        return None
    if request is None:
        return player_extras([player.user_id]).get(player.user_id)
    cache = getattr(request, "_shop_extras", None)
    if cache is None:
        cache = player_extras()
        request._shop_extras = cache
    return cache.get(player.user_id)


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
