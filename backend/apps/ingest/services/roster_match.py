"""Recognise a team by its players (NEW-TEAMS.md).

The game lobby names a team however its players typed it, so a new lobby name used to make a
brand-new team on upload. Now, when the name is unknown, the squad's UIDs decide: if at least
``MIN_MATCHING`` of them belong to one league team (its roster this season, else the team the
logs last saw them on), the squad is that team.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from apps.league.models import Player, PlayerAlias, RosterEntry, Season, Team

MIN_MATCHING = 3


@dataclass
class RosterMatch:
    team: Team
    matching: int
    of: int

    def describe(self) -> str:
        return f"{self.team.name} (matched by roster: {self.matching} of {self.of} players)"


def _players(uids: list[int]) -> dict[int, int]:
    """game UID -> player id, through merged accounts too."""
    found = dict(Player.objects.filter(game_uid__in=uids).values_list("game_uid", "pk"))
    for uid, pid in PlayerAlias.objects.filter(game_uid__in=uids).values_list(
        "game_uid", "player_id"
    ):
        found.setdefault(uid, pid)
    return found


def team_of_players(uids, season: Season | None = None) -> RosterMatch | None:
    """The one league team at least ``MIN_MATCHING`` of these UIDs play for, or None."""
    uids = [int(u) for u in uids if u]
    if len(uids) < MIN_MATCHING:
        return None
    if season is None:
        season = Season.objects.filter(is_active=True).first()
    player_of = _players(uids)
    pids = list(player_of.values())
    on_roster: dict[int, int] = {}
    if season is not None:
        on_roster = dict(
            RosterEntry.objects.filter(
                player_id__in=pids, season=season, left_on__isnull=True
            ).values_list("player_id", "team_id")
        )
    from_logs = dict(
        Player.objects.filter(pk__in=pids, current_team__isnull=False).values_list(
            "pk", "current_team_id"
        )
    )
    votes: Counter[int] = Counter()
    for pid in pids:
        team_id = on_roster.get(pid) or from_logs.get(pid)
        if team_id:
            votes[team_id] += 1
    league = set(
        Team.objects.filter(
            pk__in=votes, is_league_member=True, status=Team.Status.APPROVED
        ).values_list("pk", flat=True)
    )
    ranked = [(tid, n) for tid, n in votes.most_common() if tid in league]
    if not ranked or ranked[0][1] < MIN_MATCHING:
        return None
    if len(ranked) > 1 and ranked[1][1] == ranked[0][1]:
        return None  # a tie: don't guess
    return RosterMatch(Team.objects.get(pk=ranked[0][0]), ranked[0][1], len(uids))
