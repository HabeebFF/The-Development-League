"""MVP, Team of the week, Top kill team and Best IGL."""

import datetime as dt

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from apps.league.merge import merge_teams
from apps.league.models import Match, MatchDay, Player, ScoringRule, Season, Stage, Team
from apps.results.models import PlayerMatchRating, PlayerMatchResult, TeamMatchResult

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fresh_cache():
    cache.clear()


def player(n: int, name: str) -> Player:
    return Player.objects.create(
        game_uid=n, current_name_raw=name, display_name=name, search_name=name.lower()
    )


@pytest.fixture
def week():
    """Five matches on Tue 6 Oct 2026 between Alpha, Bravo and Charlie.

    Alpha: most points (placements), Bravo: most kills. Charlie only plays two matches.
    ACE (Alpha) rates 8.0 in all five; STAR (Charlie) rates 9.5 but only twice.
    """
    rule, _ = ScoringRule.objects.get_or_create(name="Test rule", defaults={"placement_points": {}})
    season = Season.objects.create(name="S1", scoring_rule=rule)
    stage = Stage.objects.create(season=season, name="Scrims")
    day = MatchDay.objects.create(stage=stage, number=1, date=dt.date(2026, 10, 6))
    alpha, bravo, charlie = (Team.objects.create(name=n) for n in ("Alpha", "Bravo", "Charlie"))
    ace, boss, brute, star = (
        player(1, "ACE"),
        player(2, "BOSS"),
        player(3, "BRUTE"),
        player(4, "STAR"),
    )
    for i in range(5):
        m = Match.objects.create(
            match_day=day, number=i + 1, status=Match.Status.PUBLISHED,
            started_at=dt.datetime(2026, 10, 6, 19, i * 10, tzinfo=dt.UTC),
        )  # fmt: skip
        rows = [(alpha, 1, 4, 16), (bravo, 2, 9, 15)]
        if i < 2:
            rows.append((charlie, 3, 1, 5))
        for team, place, kills, pts in rows:
            TeamMatchResult.objects.create(
                match=m, team=team, in_game_name=team.name, placement=place, kills=kills,
                placement_points=pts - kills, kill_points=kills, total_points=pts,
            )  # fmt: skip
        people = [(ace, alpha, 8.0), (brute, bravo, 7.0)]
        if i < 4:  # BOSS (Bravo's IGL) misses the last match
            people.append((boss, bravo, 6.5))
        if i < 2:
            people.append((star, charlie, 9.5))
        for p, team, rating in people:
            PlayerMatchResult.objects.create(
                match=m, player=p, team=team, raw_name=p.display_name,
                display_name=p.display_name, kills=2,
            )  # fmt: skip
            PlayerMatchRating.objects.create(
                match=m, player=p, team=team, rating=rating, raw=rating, kills=2, stamp="t"
            )
    return {"alpha": alpha, "bravo": bravo, "charlie": charlie, "ace": ace, "boss": boss}


def get(params=""):
    with override_settings(PUBLIC_SITE=True):
        resp = APIClient().get(f"/api/v1/awards{params}")
    assert resp.status_code == 200, resp.content
    data = resp.json()
    return data, {a["key"]: a for a in data["team_awards"]}


def test_mvp_needs_enough_matches(week):
    data, _ = get()
    mvp = data["mvp"]
    assert mvp["title"] == "MVP of the week"
    # STAR's 9.5 is from two matches only, so ACE wins.
    assert [p["player"] for p in mvp["top"]] == ["ACE", "BRUTE", "BOSS"]
    assert mvp["top"][0]["team"] == "Alpha" and mvp["top"][0]["value"] == 8.0
    assert mvp["top"][0]["detail"] == "8.0 average · 5 matches · 10 kills"
    # The player award list (and the player cards built from it) is unchanged.
    assert [a["key"] for a in data["awards"]] == ["player", "rusher", "sniper", "grenader"]


def test_mvp_bar_drops_when_nobody_played_enough(week):
    data, _ = get("?period=month")  # month needs 8; nobody has more than 5
    assert data["mvp"]["top"][0]["player"] == "ACE"


def test_team_of_the_week_and_kill_team(week):
    _, team = get()
    top = team["team"]["top"]
    assert [t["team"] for t in top] == ["Alpha", "Bravo", "Charlie"]
    assert top[0]["value"] == 80 and top[0]["player"] is None
    assert top[0]["detail"] == "80 points · 5 matches · 5 Booyahs · average place 1.0"
    kill = team["kill_team"]["top"]
    assert kill[0]["team"] == "Bravo" and kill[0]["value"] == 45
    assert kill[0]["detail"] == "45 kills · 5 matches · 9.0 per match"


def test_best_igl(week):
    _, team = get()
    assert team["igl"]["blocked"] and team["igl"]["top"] == []
    Team.objects.filter(pk=week["bravo"].pk).update(igl=week["boss"])
    Team.objects.filter(pk=week["alpha"].pk).update(igl=week["ace"])
    _, team = get()
    igl = team["igl"]
    assert "blocked" not in igl and igl["teams_with_igl"] == 2
    assert [p["player"] for p in igl["top"]] == ["ACE", "BOSS"]
    # BOSS's team results only count in the four matches BOSS played.
    assert igl["top"][1]["value"] == 15 and igl["top"][1]["matches"].__len__() == 4
    assert igl["top"][1]["detail"] == "15 points per match · 4 matches · average place 2.0"


def test_team_trophies_and_staff_igl_picker(week):
    with override_settings(PUBLIC_SITE=True):
        won = APIClient().get("/api/v1/team-awards/alpha").json()["awards"]
    assert {(w["kind"], w["key"]) for w in won} == {("week", "team"), ("month", "team")}

    staff = APIClient()
    staff.force_authenticate(
        get_user_model().objects.create_user(email="s@tdl.test", is_staff=True)
    )
    people = staff.get("/api/v1/admin/teams/bravo/players").json()
    assert [p["name"] for p in people] == ["BRUTE", "BOSS"] and people[0]["matches"] == 5
    resp = staff.patch("/api/v1/admin/teams/bravo", {"igl": week["boss"].pk}, format="json")
    assert resp.status_code == 200 and resp.json()["igl_name"] == "BOSS"
    resp = staff.patch("/api/v1/admin/teams/bravo", {"igl": None}, format="json")
    assert resp.json()["igl"] is None


def test_merge_keeps_igl(week):
    Team.objects.filter(pk=week["charlie"].pk).update(igl=week["boss"])
    dupe = Team.objects.create(name="Delta")
    dupe.igl = week["ace"]
    dupe.save()
    charlie = Team.objects.get(pk=week["charlie"].pk)
    merge_teams(dupe, charlie)
    charlie.refresh_from_db()
    assert charlie.igl == week["boss"]  # the kept team's IGL wins


def test_team_manager_picks_the_igl(week):
    from apps.accounts.models import Membership

    User = get_user_model()

    def member(email, team, role):
        user = User.objects.create_user(email=email)
        Membership.objects.create(user=user, team=team, role=role)
        client = APIClient()
        client.force_authenticate(user)
        return client

    manager = member("m@tdl.test", week["bravo"], Membership.Role.MANAGER)
    teammate = member("p@tdl.test", week["bravo"], Membership.Role.PLAYER)
    rival = member("r@tdl.test", week["alpha"], Membership.Role.MANAGER)
    url = "/api/v1/teams/bravo/igl"

    seen = teammate.get(url).json()
    assert seen["igl"] is None and [p["name"] for p in seen["players"]] == ["BRUTE", "BOSS"]
    assert teammate.put(url, {"igl": week["boss"].pk}, format="json").status_code == 403
    assert rival.put(url, {"igl": week["boss"].pk}, format="json").status_code == 403
    assert rival.get(url).status_code == 403
    # Only someone who has played for the team.
    assert manager.put(url, {"igl": week["ace"].pk}, format="json").status_code == 400
    resp = manager.put(url, {"igl": week["boss"].pk}, format="json")
    assert resp.status_code == 200 and resp.json()["igl_name"] == "BOSS"
    assert Team.objects.get(pk=week["bravo"].pk).igl == week["boss"]
    assert manager.put(url, {"igl": None}, format="json").json()["igl"] is None
