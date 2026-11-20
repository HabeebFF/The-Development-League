"""Each match's map, drawn at random when a night's sign-up opens and shown to everyone.

A session of 5 matches plays each active map once, in a random order. Longer sessions (a
6-map night) add random repeats, never the same map twice in a row. Staff can draw again or
set the maps by hand until the session starts; predictions price match markets for these
maps (``apps.predictions.odds``) and refund a match played on a different one.
"""

from __future__ import annotations

import random

from django.db import transaction
from django.dispatch import Signal
from django.utils import timezone

from apps.maps.models import Map

from . import services as sv
from .models import ScrimSession

DEFAULT_MATCHES = 5
DRAWS_FROM = ("open", "closed")  # sign-up has opened and the session hasn't started

# Sent (after commit) with ``scrim`` when staff change a session's maps.
maps_changed = Signal()


def pool() -> list[int]:
    """The maps that can be drawn: every active map."""
    return list(Map.objects.filter(is_active=True).order_by("name").values_list("pk", flat=True))


def matches_for(date, session: str) -> int:
    """Matches in a session (5, or what staff set for a longer night on Staff > Predictions)."""
    try:
        from apps.predictions.auto import matches_in as predictions_matches
    except ImportError:  # pragma: no cover - predictions always installed with scrims
        return DEFAULT_MATCHES
    return predictions_matches(date, session)


def matches_in(scrim: ScrimSession) -> int:
    return matches_for(scrim.date, scrim.session)


def pool_data() -> list[dict]:
    """The maps staff can pick from: ``[{id, name, slug}]``."""
    return names(pool())


def draw(count: int, maps: list[int], rng: random.Random, start: list[int] | None = None):
    """``count`` maps in match order: each map once in a random order, then random repeats,
    never the same map twice in a row. ``start`` keeps maps already drawn."""
    order = list(start or [])
    if not maps:
        return order
    while len(order) < count:
        fresh = [m for m in maps if m not in order]
        if fresh:
            rng.shuffle(fresh)
            for m in fresh:
                if len(order) < count:
                    order.append(m)
            continue
        choices = [m for m in maps if not order or m != order[-1]] or maps
        order.append(rng.choice(choices))
    return order[:count]


def ensure(scrim: ScrimSession, rng: random.Random | None = None) -> list[int]:
    """The session's maps, drawing them once sign-up has opened (or topping them up when staff
    made the session longer). Before sign-up opens there are none."""
    count = matches_in(scrim)
    if len(scrim.maps or []) >= count:
        return list(scrim.maps[:count])
    if sv.stage(scrim.date, scrim.session) not in DRAWS_FROM:
        return list(scrim.maps or [])
    maps = pool()
    if not maps:
        return list(scrim.maps or [])
    with transaction.atomic():
        row = ScrimSession.objects.select_for_update().get(pk=scrim.pk)
        if len(row.maps or []) < count:
            row.maps = draw(count, maps, rng or random.SystemRandom(), start=row.maps)
            row.maps_drawn_at = row.maps_drawn_at or timezone.now()
            row.save(update_fields=["maps", "maps_drawn_at"])
    scrim.maps, scrim.maps_drawn_at = row.maps, row.maps_drawn_at
    return list(scrim.maps[:count])


def draw_due() -> int:
    """Every few minutes: draw the maps of shown sessions whose sign-up has opened."""
    drawn = 0
    for day in sv.shown_nights():
        for session in sv.SESSIONS:
            if sv.stage(day, session) not in DRAWS_FROM:
                continue
            scrim = sv.get_session(day, session)
            before = len(scrim.maps or [])
            if len(ensure(scrim)) > before:
                drawn += 1
    return drawn


def map_for(date, session: str, number: int) -> int | None:
    """The map drawn for match ``number`` (1 = first) of a session, or None."""
    scrim = ScrimSession.objects.filter(date=date, session=session).first()
    if scrim is None:
        return None
    maps = ensure(scrim)
    return maps[number - 1] if 0 < number <= len(maps) else None


def _check_changeable(scrim: ScrimSession) -> None:
    if sv.stage(scrim.date, scrim.session) in ("started", "off"):
        raise sv.ScrimError("This session has started (or isn't a scrim night): maps are fixed.")


def redraw(scrim: ScrimSession, actor, rng: random.Random | None = None) -> list[int]:
    """Staff: draw every map again."""
    _check_changeable(scrim)
    maps = pool()
    if not maps:
        raise sv.ScrimError("There are no active maps to draw from.")
    return _save(scrim, draw(matches_in(scrim), maps, rng or random.SystemRandom()), actor)


def set_maps(scrim: ScrimSession, chosen: list, actor) -> list[int]:
    """Staff: set the maps by hand, one per match in order."""
    _check_changeable(scrim)
    count = matches_in(scrim)
    if not isinstance(chosen, list) or not all(
        isinstance(m, int) and not isinstance(m, bool) for m in chosen
    ):
        raise sv.ScrimError("Give the maps as a list of map ids, one per match.")
    if len(chosen) != count:
        raise sv.ScrimError(f"This session has {count} matches: pick {count} maps.")
    known = set(Map.objects.filter(pk__in=chosen).values_list("pk", flat=True))
    if missing := [m for m in chosen if m not in known]:
        raise sv.ScrimError(f"Unknown map id(s): {missing}.")
    return _save(scrim, chosen, actor)


def _save(scrim: ScrimSession, maps: list[int], actor) -> list[int]:
    with transaction.atomic():
        row = ScrimSession.objects.select_for_update().get(pk=scrim.pk)
        changed = row.maps != maps
        row.maps = maps
        row.maps_drawn_at = row.maps_drawn_at or timezone.now()
        row.maps_set_by = actor
        row.save(update_fields=["maps", "maps_drawn_at", "maps_set_by"])
        if changed:
            transaction.on_commit(lambda: maps_changed.send(sender=ScrimSession, scrim=row))
    scrim.maps, scrim.maps_drawn_at, scrim.maps_set_by = row.maps, row.maps_drawn_at, actor
    return maps


def names(ids: list[int]) -> list[dict]:
    """``[{id, name, slug}]`` for map ids, in the same order."""
    found = {m.pk: m for m in Map.objects.filter(pk__in=ids)}
    return [{"id": i, "name": found[i].name, "slug": found[i].slug} for i in ids if i in found]
