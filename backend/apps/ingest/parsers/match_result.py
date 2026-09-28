"""``MatchResult_<matchId>_<timestamp>.log``: final results of one match.

A team line is followed by its player lines (columns are space padded)::

    TeamName: NOOBZ ESPORTS        Rank: 1    KillScore: 17   RankScore: 12   TotalScore: 29
    NAME: NBㅤVALSIᴰˢ           ID: 2063288734           KILL: 9

- ``Rank`` is the placement in this match; teams are listed by rank in the sample
  but the parser does not rely on it.
- ``ID`` is the permanent game UID (up to 11 digits seen).
- Teams can have fewer than 4 players and there can be 12+ teams.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from .base import ParseResult, split_lines
from .filenames import FileKind, classify
from .names import display_name

_TEAM = re.compile(
    r"^\s*TeamName:\s*(?P<name>.*?)\s+Rank:\s*(?P<rank>\d+)\s+KillScore:\s*(?P<kills>-?\d+)"
    r"\s+RankScore:\s*(?P<rank_score>-?\d+)\s+TotalScore:\s*(?P<total>-?\d+)\s*$"
)
_PLAYER = re.compile(r"^\s*NAME:\s*(?P<name>.*?)\s+ID:\s*(?P<uid>\d+)\s+KILL:\s*(?P<kills>\d+)\s*$")


@dataclass
class PlayerResult:
    name_raw: str
    display_name: str
    uid: int
    kills: int


@dataclass
class TeamResult:
    name_raw: str
    name: str
    rank: int
    kill_score: int
    rank_score: int
    total_score: int
    players: list[PlayerResult] = field(default_factory=list)

    @property
    def player_kills(self) -> int:
        return sum(p.kills for p in self.players)


@dataclass
class MatchResult:
    match_id: int | None
    timestamp: datetime | None
    teams: list[TeamResult] = field(default_factory=list)

    @property
    def players(self) -> list[PlayerResult]:
        return [p for t in self.teams for p in t.players]

    def team_of(self, uid: int) -> TeamResult | None:
        for team in self.teams:
            if any(p.uid == uid for p in team.players):
                return team
        return None


def parse(filename: str, content: str | bytes) -> ParseResult[MatchResult]:
    info = classify(filename)
    data = MatchResult(
        match_id=info.match_id if info.kind is FileKind.MATCH_RESULT else None,
        timestamp=info.timestamp,
    )
    result: ParseResult[MatchResult] = ParseResult(data)
    if info.kind is not FileKind.MATCH_RESULT:
        result.warn("bad_filename", f"Not a MatchResult file name: {filename!r}")

    current: TeamResult | None = None
    seen_uids: set[int] = set()
    for line_no, line in enumerate(split_lines(content), start=1):
        if not line.strip():
            continue
        result.stats.lines += 1

        m = _TEAM.match(line)
        if m:
            current = TeamResult(
                name_raw=m["name"],
                name=display_name(m["name"]),
                rank=int(m["rank"]),
                kill_score=int(m["kills"]),
                rank_score=int(m["rank_score"]),
                total_score=int(m["total"]),
            )
            data.teams.append(current)
            result.stats.parsed += 1
            continue

        m = _PLAYER.match(line)
        if m:
            uid = int(m["uid"])
            if current is None:
                result.stats.skipped += 1
                result.warn(
                    "player_without_team", "Player line before any team line", line_no, line
                )
                continue
            if uid in seen_uids:
                result.warn("duplicate_uid", f"UID {uid} listed more than once", line_no, line)
            seen_uids.add(uid)
            current.players.append(
                PlayerResult(m["name"], display_name(m["name"]), uid, int(m["kills"]))
            )
            result.stats.parsed += 1
            continue

        result.stats.skipped += 1
        result.warn("unparsed_line", "Not a team or player line", line_no, line)

    _check(result, data)
    return result


def _check(result: ParseResult[MatchResult], data: MatchResult) -> None:
    if not data.teams:
        result.warn("no_teams", "No team lines found")
        return
    ranks: dict[int, str] = {}
    for team in data.teams:
        if team.kill_score != team.player_kills:
            result.warn(
                "kill_mismatch",
                f"{team.name}: KillScore {team.kill_score} but players have {team.player_kills}",
            )
        if team.total_score != team.kill_score + team.rank_score:
            result.warn(
                "total_mismatch",
                f"{team.name}: TotalScore {team.total_score} != KillScore + RankScore",
            )
        if not team.players:
            result.warn("empty_team", f"{team.name} has no player lines")
        if team.rank in ranks:
            result.warn(
                "duplicate_rank", f"{team.name} and {ranks[team.rank]} share rank {team.rank}"
            )
        ranks[team.rank] = team.name
