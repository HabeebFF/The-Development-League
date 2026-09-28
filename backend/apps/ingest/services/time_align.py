"""Put debugger wall-clock times and ReplayInfo game seconds on one timeline.

The debugger log has wall-clock times (the observer PC's clock); ReplayInfo has game
seconds from match start. The same kills appear in both, so the match start in
wall-clock time is the median of ``debugger_time - replay_time`` over those kills.
Without ReplayInfo, the block's start line is used (a few seconds early).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median

from ..parsers.debugger import DebuggerBlock
from ..parsers.replay_info import ReplayInfo


@dataclass(frozen=True)
class Timeline:
    start: datetime  # wall-clock time of game second 0
    method: str  # "kills" | "replay_start" | "block_start"
    samples: int = 0

    def game_seconds(self, wall: datetime) -> float:
        return round((wall - self.start).total_seconds(), 3)


def align(block: DebuggerBlock | None, replay: ReplayInfo | None) -> Timeline | None:
    if block is not None and replay is not None and replay.kills and block.kills:
        by_pair: dict[tuple[int, int], list[float]] = defaultdict(list)
        for kill in replay.kills:
            by_pair[(kill.killer_entity, kill.victim_entity)].append(kill.time)
        offsets = []
        for kill in block.kills:
            times = by_pair.get((kill.killer, kill.victim))
            if times:
                offsets.append(kill.at - timedelta(seconds=times.pop(0)))
        if offsets:
            base = offsets[0]
            deltas = [(o - base).total_seconds() for o in offsets]
            return Timeline(base + timedelta(seconds=median(deltas)), "kills", len(offsets))

    if replay is not None and replay.started_at is not None:
        return Timeline(replay.started_at, "replay_start")
    if block is not None:
        return Timeline(block.started_at, "block_start")
    return None
