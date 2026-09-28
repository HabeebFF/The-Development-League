"""``debugger-<timestamp>.log``: the client's session log (50 MB+, many matches).

Every line looks like ``[YYYY-MM-DD HH:MM:SS.mmm][thread][frame] message``. About 99%
of lines are engine noise and are skipped silently; lines without that header
(stack-trace continuations) are counted. The file is streamed line by line.

Lines we read (all verified on debugger-2026-09-26T19-41-10.log, 10 matches):

==========================  ====================================================
``EventTypeEnterGame``      a match starts (opens a block)
``SendLogEndGame ...        the match ends and names itself; the block is linked
matchid = N``               to its MatchResult by this id
``"match_id":N,"map_id":M`` map id (logged just after the end line)
``@ZX Match.AddPlayer``     ``userID`` (game UID) <-> ``playerID`` (entity id)
``OnTeamScoreInited``       in-game team name <-> TeamID
``OnTeamScoreChanged``      TeamScore per TeamID (not kills; kept raw)
``Player X Dead, killed     kill (victim, killer)
by Y``
``Player 'X' Knock Down,    knock (victim, knocker), one line per knock
by 'Y'``
``PlayKnockDownGunTrace``   repeats knocks; only used for the headshot flag
``m_ZoneStatus``            zone stage, state, outer/inner centre, inner radius
``Revive Player``           early-game respawn drop position (y is 300: the sky)
``SyncTeleportInfo``        teleport position
==========================  ====================================================

Entity ids: ``entity >> 24`` is a stable team *slot* inside one match, but it is NOT
the ``OnTeamScoreInited`` TeamID. Use ``Match.AddPlayer`` (entity -> UID) and then
MatchResult (UID -> team).

Splitting: a block runs from ``EventTypeEnterGame`` to ``SendLogEndGame``. When those
lines are missing, a new block is started by a game event outside any block, by a
zone reset (stage 0 STABLE after later stages) or by team inits after kills; such
blocks have ``match_id = None`` and are matched to a MatchResult by time later.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .base import BOM, FLOAT, ParseResult

_HEADER = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?)\]\[(\d+)\]\[(\d+)\] ?(.*)$"
)
_XYZ = rf"\(\s*{FLOAT},\s*{FLOAT},\s*{FLOAT}\s*\)"

RE_ENTER = re.compile(r"SendEventLog: EventTypeEnterGame\b")
RE_END = re.compile(r"SendLogEndGame\s+matchend matchid = (\d+)")
RE_MAP = re.compile(r'"match_id":(\d+),"map_id":(\d+)')
RE_ADD_PLAYER = re.compile(
    r"Match\.AddPlayer userID : (\d+), service_group_id : (\d+), playerID : (\d+)"
)
RE_TEAM_INIT = re.compile(r"OnTeamScoreInited -> TeamName: (.*?) TeamID: (\d+)\s*$")
RE_TEAM_SCORE = re.compile(r"OnTeamScoreChanged -> TeamID: (\d+) TeamScore: (-?\d+)")
RE_KILL = re.compile(r"^Player (\d+) Dead, killed by (\d+)")
RE_KNOCK = re.compile(r"^Player '(\d+)' Knock Down, by '(\d+)'")
RE_TRACE = re.compile(r"PlayKnockDownGunTrace killer=(\d+) victim=(\d+) headshot=(True|False)")
RE_ZONE = re.compile(
    rf"m_ZoneStatus : stageID = (\d+), OuterCenter = {_XYZ}, InnerCenter = {_XYZ}, "
    rf"InnerRadius = {FLOAT}, TimeSpanType = (ZONE_TYPE_\w+)"
)
RE_REVIVE = re.compile(rf"Revive Player (\d+), revivePosition={_XYZ}")
RE_TELEPORT = re.compile(rf"SyncTeleportInfo, Position:{_XYZ} playerID:(\d+)")

# How far apart a knock line and its gun-trace line may be to be joined.
TRACE_JOIN_WINDOW = timedelta(seconds=1)


def team_slot(entity_id: int) -> int:
    """Team slot inside a match (NOT the OnTeamScoreInited TeamID)."""
    return entity_id >> 24


def player_index(entity_id: int) -> int:
    return entity_id & 0xFFFFFF


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class Kill:
    at: datetime
    frame: int
    victim: int
    killer: int


@dataclass
class Knock:
    at: datetime
    frame: int
    victim: int
    knocker: int
    headshot: bool | None = None


@dataclass(frozen=True)
class GunTrace:
    at: datetime
    killer: int
    victim: int
    headshot: bool


@dataclass(frozen=True)
class ZoneUpdate:
    at: datetime
    stage: int
    state: str  # STABLE | PRE_SHRINK | SHRINK (or whatever the game sends)
    outer: Point
    inner: Point
    inner_radius: float


@dataclass(frozen=True)
class PositionEvent:
    at: datetime
    entity: int
    position: Point


@dataclass
class DebuggerBlock:
    """One match worth of events from the session log."""

    started_at: datetime
    start_line: int
    start_offset: int | None
    match_id: int | None = None
    map_id: int | None = None
    ended_at: datetime | None = None
    end_line: int | None = None
    end_offset: int | None = None
    implicit_start: bool = False
    players: dict[int, int] = field(default_factory=dict)  # entity -> game UID
    teams: dict[int, str] = field(default_factory=dict)  # TeamID -> in-game name
    team_scores: dict[int, int] = field(default_factory=dict)  # TeamID -> last TeamScore
    kills: list[Kill] = field(default_factory=list)
    knocks: list[Knock] = field(default_factory=list)
    zones: list[ZoneUpdate] = field(default_factory=list)
    respawns: list[PositionEvent] = field(default_factory=list)
    teleports: list[PositionEvent] = field(default_factory=list)
    _traces: list[GunTrace] = field(default_factory=list, repr=False)

    @property
    def complete(self) -> bool:
        return self.match_id is not None

    @property
    def max_zone_stage(self) -> int:
        return max((z.stage for z in self.zones), default=-1)

    def uid_of(self, entity: int) -> int | None:
        return self.players.get(entity)

    def summary(self) -> dict[str, int | None]:
        return {
            "match_id": self.match_id,
            "map_id": self.map_id,
            "players": len(self.players),
            "teams": len(self.teams),
            "kills": len(self.kills),
            "knocks": len(self.knocks),
            "headshot_knocks": sum(1 for k in self.knocks if k.headshot),
            "zone_updates": len(self.zones),
            "respawns": len(self.respawns),
            "teleports": len(self.teleports),
        }

    def _finish(self) -> None:
        """Join gun traces onto knocks for the headshot flag, then drop the traces."""
        unused = list(self._traces)
        for knock in self.knocks:
            for i, trace in enumerate(unused):
                if (
                    trace.killer == knock.knocker
                    and trace.victim == knock.victim
                    and abs(trace.at - knock.at) <= TRACE_JOIN_WINDOW
                ):
                    knock.headshot = trace.headshot
                    del unused[i]
                    break
        self._traces = []


@dataclass
class DebuggerSession:
    blocks: list[DebuggerBlock] = field(default_factory=list)
    lines_without_header: int = 0
    lines_outside_blocks: int = 0

    def block_for(self, match_id: int) -> DebuggerBlock | None:
        return next((b for b in self.blocks if b.match_id == match_id), None)


class _Splitter:
    """State machine that turns a stream of lines into match blocks."""

    def __init__(self, result: ParseResult[DebuggerSession], session: DebuggerSession):
        self.result = result
        self.session = session
        self.current: DebuggerBlock | None = None  # open block
        self.ended: DebuggerBlock | None = None  # closed, may still get its map id
        self.done: list[DebuggerBlock] = []

    # -- block lifecycle -------------------------------------------------------------

    def _open(self, at: datetime, line_no: int, offset: int | None, implicit: bool) -> None:
        self._flush_ended()
        if self.current is not None:
            self.result.warn(
                "block_without_end",
                f"Match started at {self.current.started_at} has no end line; "
                "it will be matched by time",
                line_no,
            )
            self._close(self.current, None, None, None)
        self.current = DebuggerBlock(
            started_at=at, start_line=line_no, start_offset=offset, implicit_start=implicit
        )
        if implicit:
            self.result.warn(
                "implicit_block_start", "Match events found before a match start line", line_no
            )

    def _close(
        self,
        block: DebuggerBlock,
        at: datetime | None,
        line_no: int | None,
        offset: int | None,
    ) -> None:
        block.ended_at = at
        block.end_line = line_no
        block.end_offset = offset
        block._finish()
        if block is self.current:
            self.current = None
        if block.match_id is not None:
            self._flush_ended()
            self.ended = block  # keep it around for the map id line
        else:
            self.done.append(block)

    def _flush_ended(self) -> None:
        if self.ended is not None:
            self.done.append(self.ended)
            self.ended = None

    def _block(self, at: datetime, line_no: int, offset: int | None) -> DebuggerBlock:
        if self.current is None:
            self._open(at, line_no, offset, implicit=True)
        assert self.current is not None
        return self.current

    # -- line handling ---------------------------------------------------------------

    def feed(self, at: datetime, frame: int, msg: str, line_no: int, offset: int | None) -> bool:
        """Handle one message. Returns True when the line was used."""
        if "EventTypeEnterGame" in msg and RE_ENTER.search(msg):
            self._open(at, line_no, offset, implicit=False)
            return True

        if "SendLogEndGame" in msg:
            m = self._match(RE_END, msg, "end", line_no)
            if not m:
                return False
            block = self._block(at, line_no, offset)
            block.match_id = int(m[1])
            self._close(block, at, line_no, offset)
            return True

        if '"map_id"' in msg:
            m = RE_MAP.search(msg)
            if not m:
                return False
            match_id, map_id = int(m[1]), int(m[2])
            for block in (self.ended, self.current):
                if block is not None and block.match_id == match_id:
                    block.map_id = map_id
                    return True
            if self.current is not None and self.current.match_id is None:
                self.current.map_id = map_id
                return True
            return False

        if "Match.AddPlayer" in msg:
            m = self._match(RE_ADD_PLAYER, msg, "add_player", line_no)
            if not m:
                return False
            block = self._block(at, line_no, offset)
            uid, entity = int(m[1]), int(m[3])
            previous = block.players.get(entity)
            if previous is not None and previous != uid:
                self.result.warn(
                    "entity_conflict", f"Entity {entity} added as {previous} and {uid}", line_no
                )
            block.players[entity] = uid
            return True

        if "OnTeamScoreInited" in msg:
            m = self._match(RE_TEAM_INIT, msg, "team_init", line_no)
            if not m:
                return False
            if self.current is not None and self.current.kills:
                # Team setup after kills: a new match began without a start line.
                self._open(at, line_no, offset, implicit=True)
            block = self._block(at, line_no, offset)
            block.teams[int(m[2])] = m[1].strip()
            return True

        if "OnTeamScoreChanged" in msg:
            m = self._match(RE_TEAM_SCORE, msg, "team_score", line_no)
            if not m:
                return False
            self._block(at, line_no, offset).team_scores[int(m[1])] = int(m[2])
            return True

        if "Dead, killed by" in msg:
            m = self._match(RE_KILL, msg, "kill", line_no)
            if not m:
                return False
            self._block(at, line_no, offset).kills.append(Kill(at, frame, int(m[1]), int(m[2])))
            return True

        if "Knock Down, by" in msg:
            m = self._match(RE_KNOCK, msg, "knock", line_no)
            if not m:
                return False
            self._block(at, line_no, offset).knocks.append(Knock(at, frame, int(m[1]), int(m[2])))
            return True

        if "PlayKnockDownGunTrace" in msg:
            m = self._match(RE_TRACE, msg, "gun_trace", line_no)
            if not m:
                return False
            self._block(at, line_no, offset)._traces.append(
                GunTrace(at, int(m[1]), int(m[2]), m[3] == "True")
            )
            return True

        if "m_ZoneStatus" in msg:
            m = self._match(RE_ZONE, msg, "zone", line_no)
            if not m:
                return False
            state = m[9].removeprefix("ZONE_TYPE_")
            stage = int(m[1])
            if (
                self.current is not None
                and stage == 0
                and state == "STABLE"
                and self.current.max_zone_stage >= 1
            ):
                # Zone reset without an end line: a new match began.
                self._open(at, line_no, offset, implicit=True)
            zone = ZoneUpdate(
                at=at,
                stage=stage,
                state=state,
                outer=Point(float(m[2]), float(m[3]), float(m[4])),
                inner=Point(float(m[5]), float(m[6]), float(m[7])),
                inner_radius=float(m[8]),
            )
            block = self._block(at, line_no, offset)
            last = block.zones[-1] if block.zones else None
            if last is None or (
                last.stage,
                last.state,
                last.outer,
                last.inner,
                last.inner_radius,
            ) != (
                zone.stage,
                zone.state,
                zone.outer,
                zone.inner,
                zone.inner_radius,
            ):
                block.zones.append(zone)
            return True

        if "Revive Player" in msg:
            m = self._match(RE_REVIVE, msg, "revive", line_no)
            if not m:
                return False
            point = Point(float(m[2]), float(m[3]), float(m[4]))
            self._block(at, line_no, offset).respawns.append(PositionEvent(at, int(m[1]), point))
            return True

        if "SyncTeleportInfo" in msg:
            m = self._match(RE_TELEPORT, msg, "teleport", line_no)
            if not m:
                return False
            point = Point(float(m[1]), float(m[2]), float(m[3]))
            self._block(at, line_no, offset).teleports.append(PositionEvent(at, int(m[4]), point))
            return True

        return False

    def _match(self, pattern: re.Pattern[str], msg: str, kind: str, line_no: int):
        m = pattern.search(msg)
        if m is None:
            self.result.warn(
                "malformed_line", f"Looks like a {kind} line but did not parse", line_no, msg
            )
        return m

    def finish(self) -> None:
        if self.current is not None:
            self.result.warn(
                "block_without_end",
                f"Match started at {self.current.started_at} has no end line (file ends)",
            )
            self._close(self.current, None, None, None)
        self._flush_ended()

    def drain(self) -> list[DebuggerBlock]:
        out, self.done = self.done, []
        return out


def _decode(raw: bytes | str) -> str:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    return raw.rstrip("\r\n")


def _parse_time(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None


def iter_blocks(
    lines: Iterable[bytes | str], result: ParseResult[DebuggerSession] | None = None
) -> Iterator[DebuggerBlock]:
    """Stream lines (bytes from a binary file, or str) and yield match blocks.

    Byte offsets are recorded when the input is bytes, so a block can be re-read later
    without scanning the whole file.
    """
    session = DebuggerSession()
    if result is None:
        result = ParseResult(session)
    elif result.data is None:
        result.data = session
    else:
        session = result.data
    splitter = _Splitter(result, session)

    offset = 0
    for line_no, raw in enumerate(lines, start=1):
        line_offset = offset if isinstance(raw, bytes) else None
        if isinstance(raw, bytes):
            offset += len(raw)
        line = _decode(raw)
        if line_no == 1:
            line = line.lstrip(BOM)
        result.stats.lines += 1

        m = _HEADER.match(line)
        if m is None:
            if line.strip():
                session.lines_without_header += 1
            result.stats.skipped += 1
            continue
        at = _parse_time(m[1])
        if at is None:
            result.stats.skipped += 1
            result.warn("bad_timestamp", "Unreadable timestamp", line_no, line)
            continue

        try:
            used = splitter.feed(at, int(m[3]), m[4], line_no, line_offset)
        except Exception as exc:  # never let one odd line stop an upload
            used = False
            result.warn("parser_error", f"{type(exc).__name__}: {exc}", line_no, line)
        if used:
            result.stats.parsed += 1
        else:
            result.stats.skipped += 1
            if splitter.current is None:
                session.lines_outside_blocks += 1
        yield from splitter.drain()

    splitter.finish()
    yield from splitter.drain()


def parse_stream(lines: Iterable[bytes | str]) -> ParseResult[DebuggerSession]:
    """Parse a whole session log into a ``DebuggerSession`` (events are small)."""
    result: ParseResult[DebuggerSession] = ParseResult(DebuggerSession())
    assert result.data is not None
    for block in iter_blocks(lines, result):
        result.data.blocks.append(block)
    if not result.data.blocks:
        result.warn("no_matches", "No matches found in this debugger log")
    return result


def parse_file(path: str) -> ParseResult[DebuggerSession]:
    with open(path, "rb") as fh:
        return parse_stream(fh)


__all__ = [
    "DebuggerBlock",
    "DebuggerSession",
    "GunTrace",
    "Kill",
    "Knock",
    "Point",
    "PositionEvent",
    "ZoneUpdate",
    "iter_blocks",
    "parse_file",
    "parse_stream",
    "player_index",
    "team_slot",
]
