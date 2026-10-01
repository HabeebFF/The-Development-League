"""Merge one team into another (two names for the same team).

Everything that pointed at the old team moves to the kept one: match results, player
results, rotations, replay tracks, aliases, roster, group places, members and invites.
The old team's name becomes an alias of the kept one, so the next upload with that
in-game name lands on the kept team. Then the old team is deleted.
"""

from __future__ import annotations

from django.db import transaction

from apps.accounts.models import Invite, Membership
from apps.results.models import PlayerMatchResult, StandingRow, TeamMatchResult
from apps.results.standings import schedule_rebuild
from apps.rotations.models import PlayerTrack, TeamRotation

from .models import Player, RosterEntry, Season, Team, TeamAlias


class MergeError(Exception):
    pass


@transaction.atomic
def merge_teams(source: Team, target: Team) -> dict:
    if source.pk == target.pk:
        raise MergeError("Pick a different team to merge into.")

    shared = TeamMatchResult.objects.filter(team=source, match__team_results__team=target)
    if shared.exists():
        count = shared.count()
        raise MergeError(
            f"Both teams played in the same match ({count} match{'es' if count != 1 else ''}), "
            "so they are different teams."
        )

    seasons = set(
        Season.objects.filter(stages__match_days__matches__team_results__team=source).values_list(
            "pk", flat=True
        )
    )
    moved = {
        "results": TeamMatchResult.objects.filter(team=source).update(team=target),
        "player_results": PlayerMatchResult.objects.filter(team=source).update(team=target),
        "rotations": TeamRotation.objects.filter(team=source).update(team=target),
    }
    PlayerTrack.objects.filter(team=source).update(team=target)
    Player.objects.filter(current_team=source).update(current_team=target)

    # Rows the kept team already has win: a player has one roster entry per season and a
    # user one membership per team.
    kept = set(RosterEntry.objects.filter(team=target).values_list("player_id", "season_id"))
    for entry in RosterEntry.objects.filter(team=source):
        if (entry.player_id, entry.season_id) in kept:
            entry.delete()
    RosterEntry.objects.filter(team=source).update(team=target)
    Membership.objects.filter(
        team=source, user__in=Membership.objects.filter(team=target).values("user")
    ).delete()
    Membership.objects.filter(team=source).update(team=target)
    Invite.objects.filter(team=source).update(team=target)

    for group in source.league_groups.all():
        group.teams.add(target)

    TeamAlias.objects.filter(team=source).update(team=target)
    if not TeamAlias.objects.filter(in_game_name=source.name, season=None).exists():
        TeamAlias.objects.create(team=target, in_game_name=source.name)

    StandingRow.objects.filter(team=source).delete()
    name = source.name
    source.delete()
    schedule_rebuild(*seasons)
    return {"merged": name, "into": target.slug, **moved}
