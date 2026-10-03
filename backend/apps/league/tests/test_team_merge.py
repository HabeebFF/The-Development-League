"""Merging two teams that are really one (an in-game name variant)."""

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Membership, User
from apps.coach.models import CoachReport
from apps.league.models import Group, Match, MatchDay, ScoringRule, Season, Stage, Team, TeamAlias
from apps.results.models import MatchEvent, StandingRow, TeamMatchResult
from apps.rotations.models import ReplayObject

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_client() -> APIClient:
    client = APIClient()
    client.force_authenticate(User.objects.create_user(email="s@tdl.test", is_staff=True))
    return client


@pytest.fixture
def setup():
    season = Season.objects.create(
        name="Test Season",
        slug="test",
        is_active=True,
        scoring_rule=ScoringRule.objects.get(name="TDL default"),
    )
    stage = Stage.objects.create(season=season, name="League")
    group = Group.objects.create(stage=stage, name="A")
    day = MatchDay.objects.create(stage=stage, number=11)
    m1 = Match.objects.create(match_day=day, number=1, status=Match.Status.PUBLISHED)
    m2 = Match.objects.create(match_day=day, number=2, status=Match.Status.PUBLISHED)
    kept = Team.objects.create(name="OUTPOST33 ESP")
    variant = Team.objects.create(name="OUTPOST-33 ESPO")
    other = Team.objects.create(name="NOOBZ ESPORTS")
    TeamAlias.objects.create(team=kept, in_game_name="OUTPOST33 ESP")
    TeamAlias.objects.create(team=variant, in_game_name="OUTPOST-33 ESPO")
    group.teams.add(variant)

    def result(match, team, placement):
        TeamMatchResult.objects.create(
            match=match,
            team=team,
            in_game_name=team.name,
            placement=placement,
            kills=2,
            placement_points=0,
            kill_points=0,
            total_points=0,
        )

    result(m1, kept, 3)
    result(m1, other, 1)
    result(m2, variant, 2)
    result(m2, other, 1)
    return {"season": season, "group": group, "kept": kept, "variant": variant, "other": other}


def test_merge_moves_results_and_names(staff_client, setup, django_capture_on_commit_callbacks):
    kept, variant = setup["kept"], setup["variant"]
    manager = User.objects.create_user(email="m@tdl.test")
    Membership.objects.create(user=manager, team=variant, role="MANAGER")
    with django_capture_on_commit_callbacks(execute=True):
        resp = staff_client.post(
            f"/api/v1/admin/teams/{variant.slug}/merge", {"into": kept.slug}, format="json"
        )
    assert resp.status_code == 200, resp.content
    assert resp.json()["results"] == 1
    assert not Team.objects.filter(pk=variant.pk).exists()
    assert TeamMatchResult.objects.filter(team=kept).count() == 2
    # Both spellings now resolve to the kept team, so later uploads land there too.
    names = set(kept.aliases.values_list("in_game_name", flat=True))
    assert names == {"OUTPOST33 ESP", "OUTPOST-33 ESPO"}
    assert Membership.objects.get(user=manager).team == kept
    assert kept in setup["group"].teams.all()
    row = StandingRow.objects.get(season=setup["season"], scope="season", team=kept)
    assert row.matches_played == 2


def test_merge_keeps_events_replay_objects_and_coach_reports(staff_client, setup):
    kept, variant, other = setup["kept"], setup["variant"], setup["other"]
    m2 = TeamMatchResult.objects.get(team=variant).match
    K = MatchEvent.Kind
    killed = MatchEvent.objects.create(
        match=m2, kind=K.KILL, source="DEBUGGER", actor_team=variant, target_team=other
    )
    died = MatchEvent.objects.create(
        match=m2, kind=K.KILL, source="DEBUGGER", actor_team=other, target_team=variant
    )
    uav = ReplayObject.objects.create(
        match=m2, kind=ReplayObject.Kind.PLAYER_UAV, team=variant, start_s=1, end_s=2, x=0, z=0
    )
    week, old_week = date(2026, 9, 28), date(2026, 9, 21)
    CoachReport.objects.create(team=kept, week_start=week)
    CoachReport.objects.create(team=variant, week_start=week)
    moved_report = CoachReport.objects.create(team=variant, week_start=old_week)

    resp = staff_client.post(
        f"/api/v1/admin/teams/{variant.slug}/merge", {"into": kept.slug}, format="json"
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["events"] == 2 and resp.json()["replay_objects"] == 1
    killed.refresh_from_db()
    died.refresh_from_db()
    uav.refresh_from_db()
    assert killed.actor_team == kept and died.target_team == kept and uav.team == kept
    # One report per team and week: the kept team's stays, the old week moves across.
    assert CoachReport.objects.filter(team=kept, week_start=week).count() == 1
    moved_report.refresh_from_db()
    assert moved_report.team == kept


def test_merge_refuses_teams_that_met(staff_client, setup):
    url = f"/api/v1/admin/teams/{setup['other'].slug}/merge"
    resp = staff_client.post(url, {"into": setup["kept"].slug}, format="json")
    assert resp.status_code == 400
    assert "same match" in resp.json()["detail"]
    assert Team.objects.filter(pk=setup["other"].pk).exists()


def test_merge_needs_staff_and_a_real_target(setup, staff_client):
    url = f"/api/v1/admin/teams/{setup['variant'].slug}/merge"
    assert APIClient().post(url, {"into": "x"}).status_code in (401, 403)
    assert staff_client.post(url, {"into": "nope"}, format="json").status_code == 404
    same = staff_client.post(url, {"into": setup["variant"].slug}, format="json")
    assert same.status_code == 400


def test_making_a_season_active_retires_the_old_one(staff_client, setup):
    resp = staff_client.post(
        "/api/v1/admin/seasons", {"name": "TDL Season 1", "is_active": True}, format="json"
    )
    assert resp.status_code == 201, resp.content
    assert list(Season.objects.filter(is_active=True).values_list("slug", flat=True)) == [
        "tdl-season-1"
    ]
