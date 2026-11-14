"""Player shop milestones: frames a league player earns by playing, never buys.

A design with ``unlock = "kills:100"`` is given (free) to a linked player once their career
total reaches it. Totals come straight from the match results, so they follow uploads, fixes
and removed matches. A copy already given is kept even if a fixed match drops the total back.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Sum

STATS = {
    "kills": "kills",
    "booyahs": "booyahs",
    "totw": "Team of the Week picks",
}


def parse(unlock: str) -> tuple[str, int] | None:
    """``"kills:100"`` -> ``("kills", 100)``; ``None`` for blank or bad text."""
    stat, _, n = (unlock or "").partition(":")
    if stat not in STATS or not n.isdigit() or int(n) < 1:
        return None
    return stat, int(n)


def label(unlock: str) -> str:
    parsed = parse(unlock)
    if parsed is None:
        return ""
    stat, n = parsed
    name = STATS[stat]
    if n == 1 and stat == "totw":
        return "Make the Team of the Week"
    return f"Reach {n:,} {name}"


def progress(player) -> dict[str, int]:
    """A player's career totals for every milestone stat."""
    from apps.results.models import PlayerCard, PlayerMatchResult, TeamMatchResult

    rows = PlayerMatchResult.objects.filter(player=player)
    kills = rows.aggregate(n=Sum("kills"))["n"] or 0
    won = TeamMatchResult.objects.filter(
        match=OuterRef("match"), team=OuterRef("team"), placement=1
    )
    booyahs = rows.filter(Exists(won)).count()
    totw = PlayerCard.objects.filter(player=player).exclude(totw=[]).count()
    return {"kills": kills, "booyahs": booyahs, "totw": totw}


def grant(user, player) -> list:
    """Give ``user`` every milestone design their player has reached and doesn't own yet.
    Returns the new copies."""
    from .models import CardDesign, OwnedDesign
    from .services import _next_copy

    if player is None:
        return []
    owned = set(
        OwnedDesign.objects.filter(user=user, refunded_at__isnull=True).values_list(
            "design_id", flat=True
        )
    )
    todo = [d for d in CardDesign.objects.exclude(unlock="") if d.pk not in owned]
    if not todo:
        return []
    stats = progress(player)
    new = []
    for design in todo:
        parsed = parse(design.unlock)
        if parsed is None or stats[parsed[0]] < parsed[1]:
            continue
        try:
            with transaction.atomic():
                design = CardDesign.objects.select_for_update().get(pk=design.pk)
                if design.owners.filter(user=user, refunded_at__isnull=True).exists():
                    continue
                new.append(
                    OwnedDesign.objects.create(
                        user=user,
                        design=design,
                        copy_number=_next_copy(design),
                        price_paid=0,
                        gift_note=f"Milestone: {label(design.unlock)}",
                    )
                )
        except IntegrityError:  # granted at the same moment by another request
            continue
    return new
