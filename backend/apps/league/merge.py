"""Merge one team into another (two names for the same team), or one player into another.

Everything that pointed at the old team moves to the kept one: match results, player
results, rotations, replay tracks and objects, match events, coach reports, aliases,
roster, group places, members and invites.
The old team's name becomes an alias of the kept one, so the next upload with that
in-game name lands on the kept team. Then the old team is deleted.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Invite, Membership
from apps.coach.models import CoachReport
from apps.results.models import MatchEvent, PlayerMatchResult, StandingRow, TeamMatchResult
from apps.results.standings import schedule_rebuild
from apps.rotations.models import PlayerTrack, ReplayObject, TeamRotation

from .models import Match, Player, PlayerAlias, RosterEntry, Season, Team, TeamAlias


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
        # These would otherwise lose their team when the old team is deleted (SET_NULL).
        "events": MatchEvent.objects.filter(actor_team=source).update(actor_team=target)
        + MatchEvent.objects.filter(target_team=source).update(target_team=target),
        "replay_objects": ReplayObject.objects.filter(team=source).update(team=target),
    }
    PlayerTrack.objects.filter(team=source).update(team=target)
    # One coach report per team and week: the kept team's wins (staff rewrite it to cover
    # both), the rest move.
    CoachReport.objects.filter(
        team=source, week_start__in=CoachReport.objects.filter(team=target).values("week_start")
    ).delete()
    CoachReport.objects.filter(team=source).update(team=target)
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


@transaction.atomic
def merge_players(source: Player, target: Player) -> dict:
    """Merge ``source`` into ``target`` (two accounts or names of the same person).

    Their match results, events, replay tracks, ratings and rosters move to the kept player;
    the old game UID becomes an alias so later uploads land on the kept player too. Cards are
    rebuilt for the weeks either one has a card in, and the coach's after-match reviews for
    the matches that moved.
    """
    from apps.coach.moments import review_match
    from apps.results import cards
    from apps.results.models import PlayerCard, PlayerMatchRating

    if source.pk == target.pk:
        raise MergeError("Pick a different player to merge into.")
    shared = PlayerMatchResult.objects.filter(
        player=source, match__player_results__player=target
    ).count()
    if shared:
        raise MergeError(
            f"Both players played in the same match ({shared} match{'es' if shared != 1 else ''}"
            "), so they are different people."
        )

    matches = list(
        PlayerMatchResult.objects.filter(player=source).values_list("match_id", flat=True)
    )
    weeks = set(
        PlayerCard.objects.filter(player__in=[source, target]).values_list("week", flat=True)
    )
    moved = {
        "results": PlayerMatchResult.objects.filter(player=source).update(player=target),
        "events": MatchEvent.objects.filter(actor_player=source).update(actor_player=target)
        + MatchEvent.objects.filter(target_player=source).update(target_player=target),
        "ratings": PlayerMatchRating.objects.filter(player=source).update(player=target),
    }
    PlayerTrack.objects.filter(player=source).update(player=target)
    ReplayObject.objects.filter(player=source).update(player=target)
    # One roster entry per player and season: the kept player's wins.
    kept = set(RosterEntry.objects.filter(player=target).values_list("season_id", flat=True))
    RosterEntry.objects.filter(player=source, season_id__in=kept).delete()
    RosterEntry.objects.filter(player=source).update(player=target)
    PlayerCard.objects.filter(player=source).delete()

    # What the kept player doesn't have yet comes over.
    changed = []
    for field in ("country", "photo", "photo_cutout", "card_role"):
        if not getattr(target, field) and getattr(source, field):
            setattr(target, field, getattr(source, field))
            changed.append(field)
    if target.current_team_id is None and source.current_team_id:
        target.current_team_id = source.current_team_id
        changed.append("current_team")
    target.hide_card = target.hide_card or source.hide_card
    user = source.user
    PlayerAlias.objects.filter(player=source).update(player=target)
    PlayerAlias.objects.update_or_create(
        game_uid=source.game_uid, defaults={"player": target, "name": source.display_name}
    )
    name = source.display_name
    source.delete()
    if user is not None and target.user_id is None:
        target.user = user
        changed.append("user")
    target.save(update_fields=[*changed, "hide_card", "updated_at"])

    # Cached card lines are keyed by match and its updated_at: touch the matches that moved.
    Match.objects.filter(pk__in=matches).update(updated_at=timezone.now())
    for match_id in matches:
        review_match(match_id)
    for week in sorted(weeks):
        cards.build_week(week)
    return {"merged": name, "into": target.display_name, **moved}
