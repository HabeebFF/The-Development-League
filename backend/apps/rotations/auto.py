"""Auto-drafted rotations from what the logs already tell us.

For each team and each zone phase, the median of that team's known positions in that
phase (where its players got kills, died, respawned or teleported) becomes a zone
point. Phases start when a zone starts shrinking: zone 1 is where the team was while
the first circle closed, and so on. A team's last known position becomes its FINAL
point (the winner) or ELIMINATED point (everyone else).

The drop is only suggested: the median of the team's fights (kills and deaths, not
respawns) before the first zone shrinks, which is usually near where it landed.

Only rotations still in AUTO status are rebuilt; anything staff touched is kept.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass

from django.db import transaction

from apps.league.models import Match
from apps.maps.models import MapArea
from apps.results.models import MatchEvent, TeamMatchResult, ZonePhase

from .models import MAX_ZONES, Checkpoint, RotationPoint, TeamRotation

# A team's elimination position may be logged a moment after the elimination event.
ELIMINATION_SLACK_S = 2.0


@dataclass(frozen=True)
class Sighting:
    t: float
    x: float
    z: float
    kind: str  # kills | deaths | respawns | teleports


@dataclass
class DraftPoint:
    checkpoint: str
    x: float
    z: float
    game_time_s: float | None
    evidence: dict[str, int]


def sightings(match: Match) -> dict[int, list[Sighting]]:
    """Every timed position we know per team, oldest first."""
    events = MatchEvent.objects.filter(match=match, game_time_s__isnull=False)
    has_deaths = events.filter(kind=MatchEvent.Kind.DEATH, x__isnull=False).exists()
    seen: dict[int, list[Sighting]] = defaultdict(list)
    K = MatchEvent.Kind
    for e in events.exclude(kind__in=[K.KNOCK, K.TEAM_ELIMINATED]):
        t = e.game_time_s
        if e.kind == K.KILL:
            if e.x is not None and e.actor_team_id:
                seen[e.actor_team_id].append(Sighting(t, e.x, e.z, "kills"))
            # Victim positions: DeadEvents carry the same deaths, so use them when present.
            if not has_deaths and e.tx is not None and e.target_team_id:
                seen[e.target_team_id].append(Sighting(t, e.tx, e.tz, "deaths"))
        elif e.x is not None and e.actor_team_id:
            kind = {K.DEATH: "deaths", K.RESPAWN: "respawns", K.TELEPORT: "teleports"}[e.kind]
            seen[e.actor_team_id].append(Sighting(t, e.x, e.z, kind))
    for items in seen.values():
        items.sort(key=lambda s: s.t)
    return seen


def zone_windows(match: Match) -> list[tuple[float, float]]:
    """(start, end) game seconds per zone checkpoint, from each zone's shrink start."""
    starts = sorted(
        ZonePhase.objects.filter(
            match=match, state=ZonePhase.State.SHRINK, game_time_s__isnull=False
        ).values_list("game_time_s", flat=True)
    )[:MAX_ZONES]
    ends = [*starts[1:], float("inf")] if starts else []
    return list(zip(starts, ends, strict=True))


def _point(checkpoint: str, items: list[Sighting]) -> DraftPoint:
    return DraftPoint(
        checkpoint=checkpoint,
        x=round(statistics.median(s.x for s in items), 2),
        z=round(statistics.median(s.z for s in items), 2),
        game_time_s=round(statistics.median(s.t for s in items), 2),
        evidence=dict(Counter(s.kind for s in items)),
    )


def draft_points(
    result: TeamMatchResult, seen: list[Sighting], windows: list[tuple[float, float]]
) -> list[DraftPoint]:
    eliminated = result.eliminated_at_s
    alive = [s for s in seen if eliminated is None or s.t <= eliminated + ELIMINATION_SLACK_S]
    points = []
    if windows:
        early = [s for s in alive if s.t < windows[0][0] and s.kind in ("kills", "deaths")]
        if early:
            points.append(_point(Checkpoint.DROP, early))
    for index, (start, end) in enumerate(windows, start=1):
        if eliminated is not None and eliminated < start:
            break
        in_phase = [s for s in alive if start <= s.t < end]
        if in_phase:
            points.append(_point(f"ZONE_{index}", in_phase))
    if alive:
        last = alive[-1]
        checkpoint = Checkpoint.FINAL if result.placement == 1 else Checkpoint.ELIMINATED
        if result.placement == 1 or eliminated is not None:
            points.append(_point(checkpoint, [last]))
    return points


@transaction.atomic
def draft_rotations(match: Match, *, team_ids: set[int] | None = None) -> int:
    """(Re)build AUTO rotations of a match. Returns how many rotations were drafted.

    ``team_ids`` limits the rebuild to those teams and forces it even if staff edited
    them (used by "reset to auto").
    """
    seen = sightings(match)
    windows = zone_windows(match)
    areas = list(MapArea.objects.filter(map_id=match.map_id)) if match.map_id else []
    results = TeamMatchResult.objects.filter(match=match)
    if team_ids is not None:
        results = results.filter(team_id__in=team_ids)
    else:
        # Teams no longer in the results (a re-upload remapped them) lose their auto draft.
        TeamRotation.objects.filter(match=match, status=TeamRotation.Status.AUTO).exclude(
            team_id__in=results.values("team_id")
        ).delete()

    drafted = 0
    for result in results:
        rotation, _ = TeamRotation.objects.get_or_create(match=match, team_id=result.team_id)
        if team_ids is None and rotation.status != TeamRotation.Status.AUTO:
            continue
        rotation.points.all().delete()
        rotation.status = TeamRotation.Status.AUTO
        rotation.plotted_by, rotation.confirmed_at = None, None
        rotation.save()
        RotationPoint.objects.bulk_create(
            RotationPoint(
                rotation=rotation,
                checkpoint=p.checkpoint,
                order=order,
                x=p.x,
                z=p.z,
                game_time_s=p.game_time_s,
                area=MapArea.find(None, p.x, p.z, areas=areas),
                source=RotationPoint.Source.AUTO,
                evidence=p.evidence,
            )
            for order, p in enumerate(draft_points(result, seen.get(result.team_id, []), windows))
        )
        drafted += 1
    return drafted
