"""New teams signing themselves up (design: NEW-TEAMS.md).

A team's manager creates it on the site with its name, tag, logo, country, lobby name, a
contact and a roster of 4 to 6 players (in-game name, UID, role). The creator becomes its
manager. The team waits for league staff: until it's approved it is hidden from league pages
and can't sign up for scrims. On approval each roster UID becomes a player on the team's
roster, so uploaded logs put those players on this team. Approved teams' managers keep the
roster up to date on My team > Members (the "squad").
"""

from __future__ import annotations

import datetime as dt
import json
import re

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsStaff, IsTeamManagerOrStaff

from .models import Player, PlayerAlias, RosterEntry, Season, Team, TeamAlias

MIN_PLAYERS = 4
MAX_PLAYERS = 6
ROLES = {c.value: c.label for c in Player.CardRole}
LOGO_MAX_BYTES = 2 * 1024 * 1024
_TAG = re.compile(r"^[A-Za-z0-9]{2,6}$")
_COUNTRY = re.compile(r"^[A-Z]{2}$")


class FormError(APIException):
    """A 400 whose body keeps the roster rows as they are (ValidationError would turn every
    value into a string)."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, body: dict):
        super().__init__()
        self.detail = body


# -- looking things up -------------------------------------------------------------------------


def player_by_uid(uid: int) -> Player | None:
    """The player with this game UID, or the player staff merged it into."""
    player = Player.objects.select_related("current_team").filter(game_uid=uid).first()
    if player is not None:
        return player
    alias = PlayerAlias.objects.select_related("player__current_team").filter(game_uid=uid).first()
    return alias.player if alias else None


def active_season() -> Season | None:
    return Season.objects.filter(is_active=True).first()


def roster_team(player: Player, season: Season | None) -> Team | None:
    """The approved team whose roster this player is on this season, if any."""
    if season is None:
        return None
    entry = (
        RosterEntry.objects.select_related("team")
        .filter(player=player, season=season, left_on__isnull=True)
        .first()
    )
    return entry.team if entry else None


def last_played(player: Player) -> dict | None:
    """The team and date of this player's most recent match in the logs."""
    from apps.results.models import PlayerMatchResult

    row = (
        PlayerMatchResult.objects.select_related("team", "match__match_day")
        .filter(player=player)
        .order_by("-match__started_at", "-match_id")
        .first()
    )
    if row is None:
        return None
    when = row.match.started_at.date() if row.match.started_at else row.match.match_day.date
    return {
        "team": {"name": row.team.name, "slug": row.team.slug},
        "date": when.isoformat() if when else None,
    }


def _taken_name(value: str, exclude: Team | None) -> str | None:
    """Why this name can't be used (another team's name, tag or lobby name), or None."""
    teams = Team.objects.all()
    if exclude is not None:
        teams = teams.exclude(pk=exclude.pk)
    hit = teams.filter(Q(name__iexact=value) | Q(lobby_name__iexact=value)).first()
    if hit is not None:
        return f"{hit.name} already uses this name."
    alias = TeamAlias.objects.select_related("team").filter(in_game_name__iexact=value)
    if exclude is not None:
        alias = alias.exclude(team=exclude)
    alias = alias.first()
    if alias is not None:
        return f"This is how {alias.team.name} shows in the game lobby."
    return None


# -- checking a new team ---------------------------------------------------------------------------


def check_team(data: dict, exclude: Team | None = None) -> dict[str, str]:
    """Errors for the team's own fields, by field name (empty when all is well)."""
    errors: dict[str, str] = {}
    name = (data.get("name") or "").strip()
    if not 2 <= len(name) <= 40:
        errors["name"] = "Use 2 to 40 characters."
    elif why := _taken_name(name, exclude):
        errors["name"] = why
    tag = (data.get("tag") or "").strip()
    if not _TAG.match(tag):
        errors["tag"] = "Use 2 to 6 letters or numbers."
    else:
        clash = Team.objects.exclude(status=Team.Status.REJECTED).filter(tag__iexact=tag)
        if exclude is not None:
            clash = clash.exclude(pk=exclude.pk)
        hit = clash.first()
        if hit is not None:
            errors["tag"] = f"{hit.name} already uses this tag."
    lobby = (data.get("lobby_name") or "").strip()
    if lobby and lobby.lower() != name.lower():
        if len(lobby) > 40:
            errors["lobby_name"] = "Use at most 40 characters."
        elif why := _taken_name(lobby, exclude):
            errors["lobby_name"] = why
    country = (data.get("country") or "").strip().upper()
    if not _COUNTRY.match(country):
        errors["country"] = "Pick your country."
    contact = (data.get("contact") or "").strip()
    if not 3 <= len(contact) <= 120:
        errors["contact"] = "Give a WhatsApp number or Discord name so TDL staff can reach you."
    return errors


def check_players(rows, exclude: Team | None = None, *, for_squad: bool = False) -> list[dict]:
    """Each roster row, cleaned, with an ``error`` (can't be used) or ``flag`` (staff should
    look) and what we know about the UID from the logs."""
    season = active_season()
    pending = Team.objects.filter(status=Team.Status.PENDING)
    if exclude is not None:
        pending = pending.exclude(pk=exclude.pk)
    waiting: dict[str, Team] = {}
    for team in pending:
        for row in team.pending_roster or []:
            waiting[str(row.get("uid"))] = team

    out: list[dict] = []
    seen: set[str] = set()
    for raw in rows if isinstance(rows, list) else []:
        raw = raw if isinstance(raw, dict) else {}
        uid = str(raw.get("uid") or "").strip()
        name = str(raw.get("name") or "").strip()
        role = str(raw.get("role") or "").strip().upper()
        row = {
            "uid": uid,
            "name": name,
            "role": role,
            "igl": bool(raw.get("igl")),
            "error": None,
            "flag": None,
            "known": None,
        }
        out.append(row)
        if not uid.isdigit() or not 5 <= len(uid) <= 20:
            row["error"] = "A UID is 5 to 20 digits."
            continue
        if uid in seen:
            row["error"] = "This UID is on the roster twice."
            continue
        seen.add(uid)
        if not 1 <= len(name) <= 30:
            row["error"] = "Type the in-game name (up to 30 characters)."
            continue
        if role not in ROLES:
            row["error"] = "Pick a role."
            continue
        if uid in waiting:
            row["error"] = f"This UID is on {waiting[uid].name}'s roster, waiting for staff."
            continue
        player = player_by_uid(int(uid))
        if player is None:
            row["known"] = None
            continue
        played = last_played(player)
        row["known"] = {"name": player.display_name, "last": played}
        holder = roster_team(player, season)
        if holder is not None and (exclude is None or holder.pk != exclude.pk):
            msg = f"{player.display_name} is on {holder.name}'s roster."
            if for_squad:
                row["error"] = (
                    f"{msg} Ask {holder.name}'s manager to remove them, or ask TDL staff."
                )
            else:
                row["flag"] = msg
            continue
        if played and (exclude is None or played["team"]["slug"] != exclude.slug):
            row["flag"] = f"{player.display_name} last played for {played['team']['name']}" + (
                f" on {played['date']}." if played["date"] else "."
            )
    return out


def roster_errors(rows: list[dict]) -> str | None:
    """Errors about the roster as a whole."""
    if not MIN_PLAYERS <= len(rows) <= MAX_PLAYERS:
        return f"A roster has {MIN_PLAYERS} to {MAX_PLAYERS} players."
    if sum(1 for r in rows if r["igl"]) > 1:
        return "Pick one IGL at most."
    if any(r["error"] for r in rows):
        return "Fix the players marked in red."
    return None


def _stored(rows: list[dict]) -> list[dict]:
    return [{k: r[k] for k in ("uid", "name", "role", "igl")} for r in rows]


def check_logo(value):
    if not value:
        return
    if value.size > LOGO_MAX_BYTES:
        raise ValidationError({"logo": "Logos can be at most 2 MB."})
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(value) as img:
            kind = img.format
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValidationError({"logo": "This isn't a picture we can read."}) from exc
    if kind not in {"JPEG", "PNG", "WEBP"}:
        raise ValidationError({"logo": "Use a JPEG, PNG or WebP picture."})
    value.seek(0)


# -- making, changing, approving --------------------------------------------------------------


def _roster_from(data) -> list:
    roster = data.get("roster")
    if isinstance(roster, str):
        try:
            roster = json.loads(roster)
        except ValueError as exc:
            raise ValidationError({"roster": "The roster couldn't be read."}) from exc
    return roster if isinstance(roster, list) else []


def _validate(data, exclude: Team | None) -> tuple[dict, list[dict]]:
    errors: dict = check_team(data, exclude)
    rows = check_players(_roster_from(data), exclude)
    if why := roster_errors(rows):
        errors["roster"] = why
    if errors:
        raise FormError({**errors, "players": rows})
    fields = {
        "name": data["name"].strip(),
        "tag": data["tag"].strip().upper(),
        "country": data["country"].strip().upper(),
        "contact": data["contact"].strip(),
        "lobby_name": (data.get("lobby_name") or "").strip(),
    }
    if fields["lobby_name"].lower() == fields["name"].lower():
        fields["lobby_name"] = ""
    return fields, rows


def my_application(user) -> Team | None:
    """The team this user manages that isn't approved yet."""
    from apps.accounts.models import Membership

    m = (
        Membership.objects.select_related("team")
        .filter(user=user, role=Membership.Role.MANAGER, is_active=True)
        .exclude(team__status=Team.Status.APPROVED)
        .first()
    )
    return m.team if m else None


def create_team(user, data, logo=None) -> Team:
    from apps.accounts.models import Membership

    if user.is_league_staff:
        raise ValidationError({"detail": "League staff add teams from Staff > Teams."})
    on = user.active_memberships().first()
    if on is not None:
        raise ValidationError(
            {"detail": f"You're already on {on.team.name}. Leave it before creating a team."}
        )
    fields, rows = _validate(data, None)
    check_logo(logo)
    try:
        with transaction.atomic():
            team = Team.objects.create(
                **fields,
                logo=logo or "",
                status=Team.Status.PENDING,
                is_league_member=False,
                pending_roster=_stored(rows),
                created_by=user,
            )
            Membership.objects.create(user=user, team=team, role=Membership.Role.MANAGER)
    except IntegrityError as exc:  # two people taking the same name at once
        raise ValidationError({"name": "Another team just took this name."}) from exc
    return team


def update_application(team: Team, data, logo=None) -> Team:
    """The manager changes a waiting or rejected team; it goes (back) to staff."""
    if team.status == Team.Status.APPROVED:
        raise ValidationError({"detail": "This team is already approved."})
    fields, rows = _validate(data, team)
    check_logo(logo)
    for key, value in fields.items():
        setattr(team, key, value)
    if logo:
        team.logo = logo
    team.pending_roster = _stored(rows)
    team.status = Team.Status.PENDING
    team.review_note = ""
    try:
        team.save()
    except IntegrityError as exc:
        raise ValidationError({"name": "Another team just took this name."}) from exc
    return team


def withdraw(team: Team) -> None:
    if team.status == Team.Status.APPROVED:
        raise ValidationError({"detail": "This team is already approved."})
    if team.match_results.exists():
        raise ValidationError({"detail": "This team has played matches. Ask TDL staff."})
    team.delete()


def _put_on_roster(player: Player, team: Team, season: Season | None, role: str, today) -> None:
    if season is not None:
        RosterEntry.objects.filter(player=player, season=season, left_on__isnull=True).exclude(
            team=team
        ).update(left_on=today)
        RosterEntry.objects.get_or_create(
            player=player,
            team=team,
            season=season,
            left_on=None,
            defaults={"role": ROLES.get(role, ""), "joined_on": today},
        )
    if player.current_team_id != team.pk:
        Player.objects.filter(pk=player.pk).update(current_team=team)
        player.current_team = team


def _player_for(uid: int, name: str, team: Team) -> Player:
    """The player with this UID, made now if the logs haven't seen them. The typed name only
    shows until their first match: then the in-game name from the logs takes over."""
    from apps.ingest.parsers.names import clean

    player = player_by_uid(uid)
    if player is not None:
        return player
    cleaned = clean(name)
    return Player.objects.create(
        game_uid=uid,
        current_name_raw=cleaned.raw,
        display_name=cleaned.display,
        search_name=cleaned.search,
        current_team=team,
    )


def approve(team: Team, actor) -> Team:
    if team.status != Team.Status.PENDING:
        raise ValidationError({"detail": "Only a team waiting for staff can be approved."})
    rows = check_players(team.pending_roster, team)
    bad = [r for r in rows if r["error"]]
    if bad:
        raise FormError(
            {"detail": f"{bad[0]['name'] or bad[0]['uid']}: {bad[0]['error']}", "players": rows}
        )
    season = active_season()
    today = timezone.localdate()
    with transaction.atomic():
        for row in rows:
            player = _player_for(int(row["uid"]), row["name"], team)
            _put_on_roster(player, team, season, row["role"], today)
            if row["igl"]:
                team.igl = player
        if team.lobby_name:
            TeamAlias.objects.update_or_create(
                in_game_name=team.lobby_name, season=None, defaults={"team": team}
            )
        team.status = Team.Status.APPROVED
        team.is_league_member = True
        team.plan = None  # Team.save gives league teams their plan
        team.pending_roster = []
        team.reviewed_by = actor
        team.reviewed_at = timezone.now()
        team.review_note = ""
        team.save()
    return team


def reject(team: Team, actor, reason: str) -> Team:
    if team.status != Team.Status.PENDING:
        raise ValidationError({"detail": "Only a team waiting for staff can be rejected."})
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": "Tell the manager why, so they can fix it."})
    team.status = Team.Status.REJECTED
    team.review_note = reason[:200]
    team.reviewed_by = actor
    team.reviewed_at = timezone.now()
    team.save(update_fields=["status", "review_note", "reviewed_by", "reviewed_at", "updated_at"])
    return team


# -- the squad of an approved team ---------------------------------------------------------------


def squad(team: Team) -> dict:
    season = active_season()
    entries = (
        list(
            RosterEntry.objects.select_related("player")
            .filter(team=team, season=season, left_on__isnull=True)
            .order_by("player__display_name")
        )
        if season
        else []
    )
    on = {e.player_id for e in entries}
    seen = Player.objects.filter(current_team=team).exclude(pk__in=on).order_by("display_name")
    return {
        "season": season.name if season else None,
        "max": MAX_PLAYERS,
        "players": [
            {
                "id": e.player_id,
                "name": e.player.display_name,
                "game_uid": str(e.player.game_uid),
                "role": e.role,
                "joined_on": e.joined_on.isoformat() if e.joined_on else None,
            }
            for e in entries
        ],
        "from_logs": [
            {"id": p.pk, "name": p.display_name, "game_uid": str(p.game_uid)} for p in seen
        ],
    }


def add_to_squad(team: Team, data: dict, actor) -> dict:
    if team.status != Team.Status.APPROVED:
        raise ValidationError({"detail": "Your team is still waiting for TDL staff."})
    season = active_season()
    if season is None:
        raise ValidationError({"detail": "No season is running. Ask TDL staff."})
    staff = actor.is_league_staff
    rows = check_players([data], team, for_squad=not staff)
    row = rows[0] if rows else None
    if row is None or row["error"]:
        raise FormError({"detail": row["error"] if row else "Give a UID.", "players": rows})
    active = RosterEntry.objects.filter(team=team, season=season, left_on__isnull=True)
    player = player_by_uid(int(row["uid"]))
    if player is not None and active.filter(player=player).exists():
        raise ValidationError({"detail": f"{player.display_name} is already on your roster."})
    if active.count() >= MAX_PLAYERS:
        raise ValidationError(
            {"detail": f"A roster has at most {MAX_PLAYERS} players. Remove someone first."}
        )
    with transaction.atomic():
        player = _player_for(int(row["uid"]), row["name"], team)
        _put_on_roster(player, team, season, row["role"], timezone.localdate())
    return squad(team)


def remove_from_squad(team: Team, player_id: int) -> dict:
    season = active_season()
    n = RosterEntry.objects.filter(
        team=team, season=season, player_id=player_id, left_on__isnull=True
    ).update(left_on=timezone.localdate())
    if not n:
        raise ValidationError({"detail": "That player isn't on your roster."})
    return squad(team)


# -- API ------------------------------------------------------------------------------------------


def _url(f) -> str | None:
    return f.url if f else None


def team_data(team: Team, *, staff: bool = False) -> dict:
    from apps.accounts.models import Membership

    rows = check_players(team.pending_roster, team) if team.status != Team.Status.APPROVED else []
    out = {
        "id": team.pk,
        "name": team.name,
        "tag": team.tag,
        "slug": team.slug,
        "logo": _url(team.logo),
        "country": team.country,
        "lobby_name": team.lobby_name,
        "contact": team.contact,
        "status": team.status,
        "review_note": team.review_note,
        "reviewed_at": team.reviewed_at,
        "created_at": team.created_at,
        "players": rows,
    }
    if staff:
        manager = (
            Membership.objects.select_related("user")
            .filter(team=team, role=Membership.Role.MANAGER, is_active=True)
            .first()
        )
        out["manager"] = (
            {"name": manager.user.display_name, "email": manager.user.email} if manager else None
        )
        out["reviewed_by"] = str(team.reviewed_by) if team.reviewed_by else None
    return out


class MyNewTeamView(APIView):
    """GET: my team that's waiting for staff (or rejected), and the form's limits.
    POST: create a team (multipart, ``roster`` as JSON). PATCH: change and resubmit it.
    DELETE: withdraw it."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        team = my_application(request.user)
        on = request.user.active_memberships().first()
        return Response(
            {
                "team": team_data(team) if team else None,
                "can_create": team is None and on is None and not request.user.is_league_staff,
                "on_team": {"name": on.team.name, "slug": on.team.slug} if on else None,
                "min_players": MIN_PLAYERS,
                "max_players": MAX_PLAYERS,
                "roles": ROLES,
            }
        )

    def post(self, request):
        team = create_team(request.user, request.data, request.FILES.get("logo"))
        return Response(team_data(team), status=status.HTTP_201_CREATED)

    def patch(self, request):
        team = my_application(request.user)
        if team is None:
            raise ValidationError({"detail": "You have no team waiting."})
        team = update_application(team, request.data, request.FILES.get("logo"))
        return Response(team_data(team))

    def delete(self, request):
        team = my_application(request.user)
        if team is None:
            raise ValidationError({"detail": "You have no team waiting."})
        withdraw(team)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CheckNewTeamView(APIView):
    """POST the form as it is: errors and flags while the manager types (nothing is saved)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        exclude = my_application(request.user)
        rows = check_players(_roster_from(request.data), exclude)
        return Response(
            {
                "errors": check_team(request.data, exclude),
                "players": rows,
                "roster": roster_errors(rows) if rows else None,
            }
        )


class StaffNewTeamsView(APIView):
    """New teams: waiting ones first, then the last 30 days' approved and rejected ones."""

    permission_classes = [IsStaff]

    def get(self, request):
        since = timezone.now() - dt.timedelta(days=30)
        waiting = Team.objects.filter(status=Team.Status.PENDING).order_by("created_at")
        recent = (
            Team.objects.filter(created_by__isnull=False, reviewed_at__gte=since)
            .exclude(status=Team.Status.PENDING)
            .order_by("-reviewed_at")
        )
        return Response(
            {
                "waiting": [team_data(t, staff=True) for t in waiting],
                "recent": [team_data(t, staff=True) for t in recent],
            }
        )


class StaffReviewTeamView(APIView):
    permission_classes = [IsStaff]
    action = "approve"

    def post(self, request, slug):
        team = get_object_or_404(Team, slug=slug)
        if self.action == "approve":
            approve(team, request.user)
        else:
            reject(team, request.user, request.data.get("reason", ""))
        team.refresh_from_db()
        return Response(team_data(team, staff=True))


class _SquadPermission(IsTeamManagerOrStaff):
    def has_permission(self, request, view) -> bool:
        # Everyone on the team may look at the roster; managers and staff change it.
        if request.method == "GET" and request.user and request.user.is_authenticated:
            team = view.get_team()
            if (
                request.user.is_league_staff
                or request.user.memberships.filter(team=team, is_active=True).exists()
            ):
                return True
        return super().has_permission(request, view)


class SquadView(APIView):
    """A team's roster this season. GET: the roster and players the logs saw for the team.
    POST {uid, name, role}: add a player. DELETE ?player=<id>: take one off."""

    permission_classes = [_SquadPermission]

    def get_team(self) -> Team:
        if not hasattr(self, "_team"):
            self._team = get_object_or_404(Team, slug=self.kwargs["slug"])
        return self._team

    def get(self, request, slug):
        return Response(squad(self.get_team()))

    def post(self, request, slug):
        return Response(add_to_squad(self.get_team(), request.data, request.user))

    def delete(self, request, slug):
        try:
            player_id = int(request.query_params.get("player", ""))
        except ValueError as exc:
            raise ValidationError({"detail": "Which player?"}) from exc
        return Response(remove_from_squad(self.get_team(), player_id))
