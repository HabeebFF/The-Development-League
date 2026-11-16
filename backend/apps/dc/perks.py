"""Perks DC buys: looks and shout-outs only, never anything that changes how a team plays.

Player perks are paid from the player's own wallet. Team perks are paid from the team pot,
which the team's players chip into; the manager (or, for a team with no manager, any of its
players) spends it. Pots can only be spent, never taken out.
"""

from __future__ import annotations

import datetime as dt
import re

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.league.models import Match, Player, Team
from apps.predictions.models import LedgerEntry
from apps.predictions.services import CoinError, can_play, post_entry, wallet_for

from .models import Perk, PerkPurchase, PotEntry, TeamPot

Kind = LedgerEntry.Kind
K = Perk.Key
S = PerkPurchase.Status

NAME_COLOURS = ["gold", "cyan", "crimson", "emerald", "violet", "lava", "ocean", "sniper"]
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_BANNER = 2 * 1024 * 1024
BANNER_TYPES = {"image/png", "image/jpeg", "image/webp"}


class PerkError(Exception):
    """A perk that can't be bought or changed; ``str()`` is safe to show."""


# -- who can do what -----------------------------------------------------------------------------


def player_of(user) -> Player | None:
    return Player.objects.filter(user=user).select_related("current_team").first() if user else None


def team_of(user) -> Team | None:
    """The team a user plays for (their linked player's team), else the team they manage."""
    player = player_of(user)
    if player and player.current_team_id:
        return player.current_team
    from apps.accounts.models import Membership

    m = (
        Membership.objects.filter(user=user, is_active=True, role=Membership.Role.MANAGER)
        .select_related("team")
        .first()
    )
    return m.team if m else None


def can_spend_pot(user, team: Team) -> bool:
    """The team's manager; a team with no manager lets any of its players spend."""
    from apps.accounts.models import Membership

    if user.manages(team):
        return True
    has_manager = Membership.objects.filter(
        team=team, role=Membership.Role.MANAGER, is_active=True
    ).exists()
    player = player_of(user)
    return not has_manager and bool(player and player.current_team_id == team.pk)


def _require_player(user) -> Player:
    if not can_play(user):
        raise PerkError("League staff can't buy perks.")
    player = player_of(user)
    if player is None:
        raise PerkError("Perks are for league players: link your Free Fire UID on My account.")
    return player


# -- team pot ------------------------------------------------------------------------------------


def pot_for(team: Team) -> TeamPot:
    return TeamPot.objects.get_or_create(team=team)[0]


def chip_in(user, team: Team, amount: int, key: str) -> TeamPot:
    """Move ``amount`` DC from the player's wallet into their team's pot (once per ``key``)."""
    player = _require_player(user)
    if player.current_team_id != team.pk:
        raise PerkError("You can only chip in to your own team's pot.")
    if not isinstance(amount, int) or amount < 100:
        raise PerkError("Chip in at least 100 DC.")
    with transaction.atomic():
        pot = TeamPot.objects.select_for_update().get(pk=pot_for(team).pk)
        _, created = post_entry(
            wallet_for(user),
            Kind.TEAM_POT,
            -amount,
            f"pot:{key}",
            reason=f"Into the {team.name} pot",
        )
        if created:
            pot.balance += amount
            pot.save(update_fields=["balance", "updated_at"])
            PotEntry.objects.create(
                pot=pot, user=user, amount=amount, balance_after=pot.balance, note="Chipped in"
            )
    return pot


# -- buying ------------------------------------------------------------------------------------


def perk(key: str) -> Perk:
    p = Perk.objects.filter(key=key).first()
    if p is None or not p.enabled:
        raise PerkError("That perk isn't on sale.")
    return p


def _check(p: Perk, data: dict, image, user, player: Player | None) -> dict:
    """The cleaned details for a perk, or PerkError."""
    if p.key == K.BANNER:
        if image is None:
            raise PerkError("Add a banner image (PNG, JPG or WebP, up to 2 MB).")
        if image.size > MAX_BANNER:
            raise PerkError("The banner image is over 2 MB.")
        if getattr(image, "content_type", "") not in BANNER_TYPES:
            raise PerkError("The banner must be a PNG, JPG or WebP image.")
        return {}
    if p.key == K.THEME:
        primary, secondary = data.get("primary", ""), data.get("secondary", "")
        if not HEX.match(primary or "") or not HEX.match(secondary or ""):
            raise PerkError("Pick two colours (#RRGGBB).")
        return {"primary": primary.lower(), "secondary": secondary.lower()}
    if p.key == K.SHOUTOUT:
        text = " ".join(str(data.get("text", "")).split())
        if not 3 <= len(text) <= 120:
            raise PerkError("A shoutout is 3 to 120 characters.")
        return {"text": text}
    if p.key == K.PIN:
        try:
            match_id = int(data.get("match_id"))
        except (TypeError, ValueError) as exc:
            raise PerkError("Pick one of your matches.") from exc
        match = Match.objects.filter(pk=match_id, status=Match.Status.PUBLISHED).first()
        if match is None or not match.player_results.filter(player=player).exists():
            raise PerkError("Pick a match you played in.")
        at = data.get("at_s")
        try:
            at = None if at in (None, "") else max(0, min(int(at), 3600))
        except (TypeError, ValueError) as exc:
            raise PerkError("The moment is a time in seconds.") from exc
        note = " ".join(str(data.get("note", "")).split())[:80]
        return {"match_id": match.pk, "at_s": at, "note": note}
    if p.key == K.NAME_COLOUR:
        colour = data.get("colour")
        if colour not in NAME_COLOURS:
            raise PerkError("Pick one of the colours.")
        return {"colour": colour}
    raise PerkError("That perk isn't on sale.")


def buy(user, key: str, data: dict, key_once: str, image=None) -> PerkPurchase:
    """Buy a perk. Player perks come out of the wallet, team perks out of the team pot."""
    p = perk(key)
    player = _require_player(user)
    team = player.current_team
    if p.for_team:
        if team is None:
            raise PerkError("You're not on a team yet.")
        if not can_spend_pot(user, team):
            raise PerkError("Only your team's manager can spend the team pot.")
    clean = _check(p, data or {}, image, user, player)
    now = timezone.now()
    with transaction.atomic():
        done = PerkPurchase.objects.filter(data__once=key_once, user=user).first()
        if done:
            return done
        if p.for_team:
            pot = TeamPot.objects.select_for_update().get(pk=pot_for(team).pk)
            if pot.balance < p.price:
                raise PerkError(f"The team pot has {pot.balance:,} DC; this costs {p.price:,}.")
            pot.balance -= p.price
            pot.save(update_fields=["balance", "updated_at"])
            PotEntry.objects.create(
                pot=pot,
                user=user,
                amount=-p.price,
                balance_after=pot.balance,
                note=p.get_key_display(),
            )
        else:
            try:
                post_entry(
                    wallet_for(user),
                    Kind.PERK,
                    -p.price,
                    f"perk:{key_once}",
                    reason=p.get_key_display(),
                )
            except CoinError as exc:
                raise PerkError(str(exc)) from exc
        status = S.PENDING if p.key == K.SHOUTOUT else S.ACTIVE
        starts = None if status == S.PENDING else now
        if p.key == K.NAME_COLOUR:
            # A second colour starts when the current one ends, so no days are lost.
            current = _active(K.NAME_COLOUR).filter(player=player).order_by("-ends_at").first()
            if current and current.ends_at and current.ends_at > now:
                starts = current.ends_at
        ends = starts + dt.timedelta(days=p.days) if (starts and p.days) else None
        row = PerkPurchase.objects.create(
            perk=p,
            user=user,
            player=player,
            team=team if p.for_team else player.current_team,
            price_paid=p.price,
            from_pot=p.for_team,
            status=status,
            data={**clean, "once": key_once},
            starts_at=starts,
            ends_at=ends,
        )
        if image is not None:
            row.image.save(f"{team.slug}-{row.pk}{_ext(image)}", image, save=True)
        if p.key in (K.BANNER, K.THEME, K.PIN):
            scope = Q(team=team) if p.for_team else Q(player=player)
            PerkPurchase.objects.filter(scope, perk=p, status=S.ACTIVE).exclude(pk=row.pk).update(
                status=S.REPLACED
            )
        if p.key == K.THEME:
            Team.objects.filter(pk=team.pk).update(
                primary_color=clean["primary"], secondary_color=clean["secondary"]
            )
    return row


def _ext(image) -> str:
    return {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(
        getattr(image, "content_type", ""), ""
    )


# -- staff ---------------------------------------------------------------------------------------


def refund(row: PerkPurchase, staff, note: str = "") -> None:
    """Give the DC back: to the pot for team perks, to the buyer's wallet otherwise."""
    if row.from_pot:
        with transaction.atomic():
            pot = TeamPot.objects.select_for_update().get(pk=pot_for(row.team).pk)
            pot.balance += row.price_paid
            pot.save(update_fields=["balance", "updated_at"])
            PotEntry.objects.create(
                pot=pot,
                user=staff,
                amount=row.price_paid,
                balance_after=pot.balance,
                note=f"Refund: {row.perk.get_key_display()}",
            )
    else:
        post_entry(
            wallet_for(row.user),
            Kind.PERK_REFUND,
            row.price_paid,
            f"perk-refund:{row.pk}",
            reason=f"Refund: {row.perk.get_key_display()}" + (f" ({note})" if note else ""),
            actor=staff,
        )


def review(row: PerkPurchase, staff, approve: bool, note: str = "") -> PerkPurchase:
    """Approve a shoutout (it runs for the next day) or turn it down (refunded)."""
    with transaction.atomic():
        row = PerkPurchase.objects.select_for_update().get(pk=row.pk)
        if row.status != S.PENDING:
            raise PerkError("This one was already reviewed.")
        row.reviewed_by, row.review_note = staff, note[:200]
        if approve:
            now = timezone.now()
            row.status, row.starts_at = S.ACTIVE, now
            row.ends_at = now + dt.timedelta(days=row.perk.days or 1)
        else:
            row.status = S.REJECTED
            refund(row, staff, note)
        row.save()
    return row


def remove(row: PerkPurchase, staff, give_back: bool, note: str = "") -> PerkPurchase:
    """Take a perk down (a banner nobody should see, say), with or without a refund."""
    with transaction.atomic():
        row = PerkPurchase.objects.select_for_update().get(pk=row.pk)
        if row.status not in (S.ACTIVE, S.PENDING):
            raise PerkError("It isn't showing.")
        row.status, row.reviewed_by, row.review_note = S.REMOVED, staff, note[:200]
        row.save(update_fields=["status", "reviewed_by", "review_note"])
        if give_back:
            refund(row, staff, note)
    return row


# -- what the site shows -------------------------------------------------------------------------


def _active(key: str):
    now = timezone.now()
    return PerkPurchase.objects.filter(perk__key=key, status=S.ACTIVE).filter(
        Q(starts_at__isnull=True) | Q(starts_at__lte=now),
        Q(ends_at__isnull=True) | Q(ends_at__gt=now),
    )


def team_look(team: Team) -> dict:
    banner = _active(K.BANNER).filter(team=team).order_by("-starts_at").first()
    return {
        "banner": banner.image.url if banner and banner.image else None,
        "banner_until": banner.ends_at if banner else None,
    }


def shoutouts() -> list[dict]:
    rows = _active(K.SHOUTOUT).select_related("player", "team").order_by("starts_at")[:20]
    return [
        {
            "id": r.pk,
            "text": r.data.get("text", ""),
            "player_id": r.player_id,
            "name": r.player.display_name if r.player else "",
            "team": r.team.name if r.team else None,
        }
        for r in rows
    ]


def name_colours() -> dict[int, str]:
    return {
        r.player_id: r.data.get("colour")
        for r in _active(K.NAME_COLOUR).exclude(player__isnull=True)
        if r.data.get("colour")
    }


def pinned(player: Player) -> dict | None:
    row = _active(K.PIN).filter(player=player).select_related().order_by("-starts_at").first()
    if row is None:
        return None
    match = Match.objects.filter(pk=row.data.get("match_id")).select_related("match_day").first()
    if match is None:
        return None
    return {
        "match_id": match.pk,
        "label": f"{match.match_day} · Match {match.number}",
        "at_s": row.data.get("at_s"),
        "note": row.data.get("note", ""),
    }


def banners() -> dict[int, str]:
    """``{team_id: banner url}`` for every team with a banner showing (standings rows)."""
    return {r.team_id: r.image.url for r in _active(K.BANNER).exclude(team__isnull=True) if r.image}
