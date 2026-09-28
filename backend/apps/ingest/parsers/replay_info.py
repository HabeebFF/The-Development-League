"""``ReplayInfo_<matchId>_<timestamp>.json``: replay metadata written by the client.

What we use (verified on match 2103980121133858816):

- Meta: ``MatchID``, ``MapID``, ``RoomName``, ``MatchDateTime``, ``GameTotalTime``,
  ``PlayerCount``.
- ``Events`` (times are game seconds from match start):
    - ``Event 1``: a team was eliminated. ``SParam`` = in-game team name. The order
      matched the MatchResult ranks exactly.
    - ``Event 3`` + ``Event 4`` at the same time: one kill. ``Event 3.PlayerID`` is the
      killer, ``Event 4.PlayerID`` the victim (``SParam`` holds the other one's name).
      Matched the debugger ``Dead, killed by`` lines 89 for 89.
    - ``Event 2`` / ``Event 5``: meaning unknown, kept raw.
- ``PlayerHighlightUserIDs[i]`` is the game UID of ``PlayerHighlightInfos[i].PlayerID``
  (the in-match entity id). Players with no highlights are missing.
- ``PlayerHighlightInfos[i].KillEvents``: highlight-worthy actions with the actor's
  and the victim's world position (``EventID`` mixes kills, knocks and other
  highlight kinds, so it is kept raw). ``DeadEvents``: the player's deaths with
  position (a player can die more than once because of early respawns).

The sibling ``.bin`` file is a binary replay stream and is not parsed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .base import ParseResult, parse_filename_timestamp, to_text

EVENT_TEAM_ELIMINATED = 1
EVENT_KILLER = 3
EVENT_VICTIM = 4

# Max time between the killer and victim halves of one kill.
KILL_PAIR_WINDOW_S = 0.05


@dataclass(frozen=True)
class Position:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class TeamEliminated:
    time: float
    team_name: str
    entity_id: int


@dataclass(frozen=True)
class Kill:
    time: float
    killer_entity: int
    victim_entity: int
    killer_name: str
    victim_name: str


@dataclass(frozen=True)
class HighlightAction:
    """One entry of ``KillEvents``: the actor hit/knocked/killed someone."""

    time: float
    entity_id: int
    event_id: int
    weapon_id: int | None
    position: Position | None
    victim_position: Position | None


@dataclass(frozen=True)
class Death:
    time: float
    entity_id: int
    event_id: int
    position: Position | None


@dataclass(frozen=True)
class RawEvent:
    event: int
    entity_id: int
    time: float
    fparam: float
    sparam: str


@dataclass
class ReplayInfo:
    match_id: int | None
    map_id: int | None
    room_name: str
    started_at: datetime | None
    duration_s: float | None
    player_count: int | None
    entity_to_uid: dict[int, int] = field(default_factory=dict)
    eliminations: list[TeamEliminated] = field(default_factory=list)
    kills: list[Kill] = field(default_factory=list)
    actions: list[HighlightAction] = field(default_factory=list)
    deaths: list[Death] = field(default_factory=list)
    other_events: list[RawEvent] = field(default_factory=list)


def parse(filename: str, content: str | bytes) -> ParseResult[ReplayInfo]:
    result: ParseResult[ReplayInfo] = ParseResult(None)
    try:
        doc = json.loads(to_text(content))
    except (ValueError, UnicodeDecodeError) as exc:
        result.warn("bad_json", f"{filename}: not valid JSON ({exc})")
        return result
    if not isinstance(doc, dict):
        result.warn("bad_json", f"{filename}: top level is not an object")
        return result

    data = ReplayInfo(
        match_id=_int(doc.get("MatchID")),
        map_id=_int(doc.get("MapID")),
        room_name=str(doc.get("RoomName") or ""),
        started_at=parse_filename_timestamp(str(doc.get("MatchDateTime") or "")),
        duration_s=_float(doc.get("GameTotalTime")),
        player_count=_int(doc.get("PlayerCount")),
    )
    result.data = data
    if data.match_id is None:
        result.warn("missing_field", "MatchID missing")

    _parse_events(result, data, doc.get("Events"))
    _parse_highlights(
        result, data, doc.get("PlayerHighlightUserIDs"), doc.get("PlayerHighlightInfos")
    )
    return result


def _parse_events(result: ParseResult[ReplayInfo], data: ReplayInfo, events: Any) -> None:
    if not isinstance(events, list):
        result.warn("missing_field", "Events missing")
        return

    halves: list[dict] = []  # killer (3) and victim (4) events, in file order
    for raw in events:
        result.stats.lines += 1
        if not isinstance(raw, dict):
            result.stats.skipped += 1
            result.warn("bad_event", "Event is not an object")
            continue
        kind, entity, time = (
            _int(raw.get("Event")),
            _int(raw.get("PlayerID")),
            _float(raw.get("Time")),
        )
        if kind is None or entity is None or time is None:
            result.stats.skipped += 1
            result.warn("bad_event", f"Event missing Event/PlayerID/Time: {raw}")
            continue
        sparam = str(raw.get("SParam") or "")
        result.stats.parsed += 1
        if kind == EVENT_TEAM_ELIMINATED:
            data.eliminations.append(TeamEliminated(time, sparam, entity))
        elif kind in (EVENT_KILLER, EVENT_VICTIM):
            halves.append(raw)
        else:
            data.other_events.append(
                RawEvent(kind, entity, time, _float(raw.get("FParam")) or 0.0, sparam)
            )

    _pair_kills(result, data, halves)

    data.eliminations.sort(key=lambda e: e.time)


def _pair_kills(result: ParseResult[ReplayInfo], data: ReplayInfo, halves: list[dict]) -> None:
    """Join each killer event with the victim event logged next to it.

    The two halves are adjacent in the file (victim first in the sample) and their times
    can differ by a millisecond, so they are paired by order and a small time window.
    """
    i = 0
    while i < len(halves):
        a = halves[i]
        b = halves[i + 1] if i + 1 < len(halves) else None
        if (
            b is not None
            and {int(a["Event"]), int(b["Event"])} == {EVENT_KILLER, EVENT_VICTIM}
            and abs(float(a["Time"]) - float(b["Time"])) <= KILL_PAIR_WINDOW_S
        ):
            killer, victim = (a, b) if int(a["Event"]) == EVENT_KILLER else (b, a)
            data.kills.append(
                Kill(
                    time=float(killer["Time"]),
                    killer_entity=int(killer["PlayerID"]),
                    victim_entity=int(victim["PlayerID"]),
                    killer_name=str(victim.get("SParam") or ""),
                    victim_name=str(killer.get("SParam") or ""),
                )
            )
            i += 2
        else:
            result.warn("unpaired_kill", f"Kill event at t={float(a['Time']):.3f} has no partner")
            i += 1


def _parse_highlights(
    result: ParseResult[ReplayInfo], data: ReplayInfo, uids: Any, infos: Any
) -> None:
    if not isinstance(infos, list):
        result.warn("missing_field", "PlayerHighlightInfos missing")
        return
    if not isinstance(uids, list) or len(uids) != len(infos):
        result.warn("uid_list_mismatch", "PlayerHighlightUserIDs does not line up with infos")
        uids = [None] * len(infos)

    for uid, info in zip(uids, infos, strict=True):
        if not isinstance(info, dict):
            result.warn("bad_highlight", "Highlight info is not an object")
            continue
        entity = _int(info.get("PlayerID"))
        if entity is None:
            result.warn("bad_highlight", "Highlight info without PlayerID")
            continue
        uid_int = _int(uid)
        if uid_int is not None:
            previous = data.entity_to_uid.get(entity)
            if previous is not None and previous != uid_int:
                result.warn("uid_conflict", f"Entity {entity} maps to {previous} and {uid_int}")
            data.entity_to_uid[entity] = uid_int

        for ev in info.get("KillEvents") or []:
            time = _float(ev.get("TriggerPoint"))
            if time is None:
                continue
            data.actions.append(
                HighlightAction(
                    time=time,
                    entity_id=_int(ev.get("PlayerID")) or entity,
                    event_id=_int(ev.get("EventID")) or 0,
                    weapon_id=_int(ev.get("weaponDataID")),
                    position=_pos(ev.get("position")),
                    victim_position=_pos(ev.get("beKilledPlayerPos")),
                )
            )
        for ev in info.get("DeadEvents") or []:
            time = _float(ev.get("TriggerPoint"))
            if time is None:
                continue
            data.deaths.append(
                Death(
                    time=time,
                    entity_id=_int(ev.get("PlayerID")) or entity,
                    event_id=_int(ev.get("EventID")) or 0,
                    position=_pos(ev.get("position")),
                )
            )

    data.actions.sort(key=lambda a: a.time)
    data.deaths.sort(key=lambda d: d.time)


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pos(value: Any) -> Position | None:
    if not isinstance(value, dict):
        return None
    x, y, z = _float(value.get("x")), _float(value.get("y")), _float(value.get("z"))
    if x is None or y is None or z is None:
        return None
    return Position(x, y, z)
