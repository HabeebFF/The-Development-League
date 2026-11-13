"""Scrim registration endpoints: the public lobby, a team's sign-up, and Staff > Scrims."""

from __future__ import annotations

import datetime as dt

from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.league.models import Team
from apps.league.serializers import TeamRefSerializer
from common.permissions import IsStaff, IsTeamManagerOrStaff, IsTeamMemberOrStaff, PublicRead

from . import services as sv
from .models import Registration, ScrimLog, ScrimSession, ScrimSettings, Suspension

R = Registration.Status


def _date(raw, default=None) -> dt.date:
    if not raw:
        if default is None:
            raise ValidationError({"date": "Pick a date."})
        return default
    try:
        return dt.date.fromisoformat(str(raw))
    except ValueError as exc:
        raise ValidationError({"date": "Dates look like 2026-11-16."}) from exc


def _session(raw: str) -> str:
    key = str(raw).upper()
    if key not in sv.SESSIONS:
        raise ValidationError({"session": "Sessions are 8PM and 10PM."})
    return key


def _fail(exc: sv.ScrimError):
    return ValidationError({"detail": str(exc)})


def _find(date: dt.date, session: str) -> ScrimSession | None:
    return ScrimSession.objects.filter(date=date, session=session).first()


def _team(team: Team, request) -> dict:
    return TeamRefSerializer(team, context={"request": request}).data


def session_data(date: dt.date, session: str, request, *, staff=False, conf=None) -> dict:
    """One session as every page shows it; ``staff`` adds who signed each team up and when."""
    conf = conf or ScrimSettings.get()
    scrim = _find(date, session)
    rows = (
        list(scrim.registrations.select_related("team", "registered_by").order_by("created_at"))
        if scrim
        else []
    )

    def entry(row: Registration) -> dict:
        data = {"team": _team(row.team, request), "by_staff": row.by_staff}
        if staff:
            by = row.registered_by
            data["registered_by"] = (by.display_name or by.email) if by else None
            data["at"] = row.created_at
        return data

    return {
        "date": date,
        "session": session,
        "stage": sv.stage(date, session, conf),
        "opens_at": sv.opens_at(date, conf),
        "closes_at": sv.closes_at(date, session, conf),
        "starts_at": sv.starts_at(date, session),
        "max_teams": scrim.max_teams if scrim else conf.max_teams,
        "playing": [entry(r) for r in rows if r.status == R.REGISTERED],
        "waitlist": [entry(r) for r in rows if r.status == R.WAITLIST],
    }


def night_data(date, request, **kw) -> dict:
    conf = ScrimSettings.get()
    return {
        "date": date,
        "sessions": [session_data(date, s, request, conf=conf, **kw) for s in sv.SESSIONS]
        if date
        else [],
    }


def suspension_data(held: Suspension | None) -> dict | None:
    if held is None:
        return None
    return {"reason": held.reason, "until": held.until, "since": held.started_at}


# -- public ----------------------------------------------------------------------------------------


class TonightView(APIView):
    """Tonight's (or the next scrim night's) sessions and who's playing."""

    permission_classes = [PublicRead]

    def get(self, request):
        return Response(night_data(sv.next_scrim_night(), request))


# -- team ------------------------------------------------------------------------------------------


class TeamScoped(APIView):
    def get_team(self) -> Team:
        if not hasattr(self, "_team"):
            self._team = get_object_or_404(Team, slug=self.kwargs["slug"])
        return self._team


def team_night(team: Team, request) -> dict:
    """The team's next scrim night: each session, with the team's place in it."""
    data = night_data(sv.next_scrim_night(), request)
    mine = {}
    if data["date"]:
        mine = dict(
            Registration.objects.filter(team=team, scrim__date=data["date"]).values_list(
                "scrim__session", "status"
            )
        )
    for item in data["sessions"]:
        item["mine"] = mine.get(item["session"])
        if item["mine"] == R.WAITLIST:
            ids = [w["team"]["id"] for w in item["waitlist"]]
            item["waitlist_place"] = ids.index(team.pk) + 1
    user = request.user
    data["team"] = _team(team, request)
    data["can_manage"] = bool(user.is_league_staff or user.manages(team))
    data["suspended"] = suspension_data(sv.active_suspension(team))
    return data


class TeamScrimsView(TeamScoped):
    permission_classes = [IsTeamMemberOrStaff]

    def get(self, request, slug):
        return Response(team_night(self.get_team(), request))


class TeamSignupView(TeamScoped):
    """POST .../register or .../withdraw for one session of today."""

    permission_classes = [IsTeamManagerOrStaff]
    action = "register"

    def post(self, request, slug, date, session):
        team, day, key = self.get_team(), _date(date), _session(session)
        if self.action == "register":
            try:
                sv.register(sv.get_session(day, key), team, request.user)
            except sv.ScrimError as exc:
                raise _fail(exc) from exc
        else:
            scrim = _find(day, key)
            try:
                if scrim is None:
                    raise sv.ScrimError(f"{team.name} isn't signed up for this session.")
                sv.withdraw(scrim, team, request.user)
            except sv.ScrimError as exc:
                raise _fail(exc) from exc
        return Response(team_night(team, request))


# -- staff -----------------------------------------------------------------------------------------


class SettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScrimSettings
        fields = ["weekdays", "skip_dates", "opens_at", "closes_at", "max_teams", "updated_at"]
        read_only_fields = ["updated_at"]

    def validate_weekdays(self, value):
        if not isinstance(value, list) or any(d not in range(7) for d in value):
            raise serializers.ValidationError("Weekdays are 0 (Monday) to 6 (Sunday).")
        return sorted(set(value))

    def validate_skip_dates(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("A list of dates.")
        try:
            return sorted({dt.date.fromisoformat(str(d)).isoformat() for d in value})
        except ValueError as exc:
            raise serializers.ValidationError("Dates look like 2026-11-16.") from exc

    def validate_closes_at(self, value):
        if not isinstance(value, dict) or set(value) != set(sv.SESSIONS):
            raise serializers.ValidationError("Give a close time for 8PM and 10PM.")
        out = {}
        for key, raw in value.items():
            try:
                time = dt.time.fromisoformat(str(raw))
            except ValueError as exc:
                raise serializers.ValidationError("Times look like 18:00.") from exc
            if time >= sv.SESSIONS[key]:
                raise serializers.ValidationError(f"{key} sign-up must close before it starts.")
            out[key] = time.strftime("%H:%M")
        return out

    def validate(self, attrs):
        opens = attrs.get("opens_at", self.instance.opens_at)
        closes = attrs.get("closes_at", self.instance.closes_at)
        if any(dt.time.fromisoformat(v) <= opens for v in closes.values()):
            raise serializers.ValidationError({"closes_at": "Sign-up must close after it opens."})
        return attrs

    def validate_max_teams(self, value):
        if not 2 <= value <= 50:
            raise serializers.ValidationError("2 to 50 places.")
        return value


class StaffSettingsView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        return Response(SettingsSerializer(ScrimSettings.get()).data)

    def patch(self, request):
        data = SettingsSerializer(ScrimSettings.get(), data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        data.save(updated_by=request.user)
        return self.get(request)


class StaffNightView(APIView):
    """GET ?date=: that night's sessions in full (default: the next scrim night)."""

    permission_classes = [IsStaff]

    def get(self, request):
        date = _date(request.query_params.get("date"), sv.next_scrim_night() or sv.today())
        data = night_data(date, request, staff=True)
        data["scrim_night"] = sv.is_scrim_night(date)
        return Response(data)


class StaffSessionView(APIView):
    """PATCH {max_teams}; POST .../add or .../remove {team, note}."""

    permission_classes = [IsStaff]
    action = None

    def _reply(self, request, day, key):
        return Response(session_data(day, key, request, staff=True))

    def patch(self, request, date, session):
        day, key = _date(date), _session(session)
        try:
            places = int(request.data.get("max_teams"))
        except (TypeError, ValueError) as exc:
            raise ValidationError({"max_teams": "A number of places."}) from exc
        try:
            sv.set_max_teams(sv.get_session(day, key), places, request.user)
        except sv.ScrimError as exc:
            raise _fail(exc) from exc
        return self._reply(request, day, key)

    def post(self, request, date, session):
        day, key = _date(date), _session(session)
        team = get_object_or_404(Team, pk=request.data.get("team"))
        note = str(request.data.get("note") or "")[:300]
        try:
            if self.action == "add":
                sv.staff_add(sv.get_session(day, key), team, request.user, note)
            else:
                scrim = _find(day, key)
                if scrim is None:
                    raise sv.ScrimError(f"{team.name} isn't in this session.")
                sv.staff_remove(scrim, team, request.user, note)
        except sv.ScrimError as exc:
            raise _fail(exc) from exc
        return self._reply(request, day, key)


class StaffTeamsView(APIView):
    """Every team, with its suspension (if any), for the suspend list and the add picker."""

    permission_classes = [IsStaff]

    def get(self, request):
        held = {s.team_id: s for s in sv.active_suspensions()}
        teams = Team.objects.order_by("name")
        return Response(
            [{**_team(t, request), "suspended": suspension_data(held.get(t.pk))} for t in teams]
        )


class StaffSuspendView(APIView):
    """POST teams/<slug>/suspend {reason, until} or .../unsuspend."""

    permission_classes = [IsStaff]
    action = "suspend"

    def post(self, request, slug):
        team = get_object_or_404(Team, slug=slug)
        try:
            if self.action == "suspend":
                until = request.data.get("until")
                sv.suspend(
                    team,
                    request.user,
                    str(request.data.get("reason") or "")[:300],
                    _date(until) if until else None,
                )
            else:
                sv.unsuspend(team, request.user)
        except sv.ScrimError as exc:
            raise _fail(exc) from exc
        return Response(
            {**_team(team, request), "suspended": suspension_data(sv.active_suspension(team))}
        )


class StaffLogView(APIView):
    """GET ?date= (that night's sessions) and/or ?team=<slug>: newest first, 200 at most."""

    permission_classes = [IsStaff]

    def get(self, request):
        rows = ScrimLog.objects.select_related("team", "actor", "scrim")
        if request.query_params.get("date"):
            rows = rows.filter(scrim__date=_date(request.query_params["date"]))
        if request.query_params.get("team"):
            rows = rows.filter(team__slug=request.query_params["team"])
        return Response(
            [
                {
                    "at": r.at,
                    "team": r.team.name,
                    "action": r.action,
                    "label": r.get_action_display(),
                    "session": f"{r.scrim.date} {r.scrim.session}" if r.scrim else None,
                    "by": (r.actor.display_name or r.actor.email) if r.actor else None,
                    "note": r.note,
                }
                for r in rows[:200]
            ]
        )
