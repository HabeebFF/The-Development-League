"""Protection Points: tasks checked from the matches, the table, overrides and starting PP."""

import datetime as dt

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import StaffProfile, User
from apps.league.models import Match, MatchDay, Player, ScoringRule, Season, Stage, Team
from apps.protection.models import Adjustment, Period, Task
from apps.protection.rules import check_task, parse_table, refresh_season, table
from apps.results.models import MatchEvent, PlayerMatchResult, TeamMatchResult, ZonePhase

pytestmark = pytest.mark.django_db
K = MatchEvent.Kind
DAY = dt.date(2026, 10, 12)
ZONE5_AT = 900.0  # zone 5 appears at 900 s in every match below

OLD_TABLE = """🔥 CURRENT PROTECTION POINT STANDINGS 🔥

🟢 POSITIVE PROTECTION POINTS

1. ALPHA — +4 PP
2. BRAVO ESPORTS — +2 PP

⚪ ZERO PROTECTION POINTS

3. CHARLIE — 0 PP

🔴 NEGATIVE PROTECTION POINTS

4. OUTPOST 33 — -1 PP
5. NOBODY FC — -1 PP

━━━━━━━━━━━━━━━━━━
📊 TOTAL: 5 TEAMS
"""


def player(n: int) -> Player:
    return Player.objects.create(
        game_uid=n, current_name_raw=f"P{n}", display_name=f"P{n}", search_name=f"p{n}"
    )


@pytest.fixture
def league():
    """Alpha and Bravo play 5 matches on DAY; Charlie plays only the first.

    Alpha: whole squad at zone 5 in matches 1-4 (P1 dies early in match 1 but respawns),
    loses P2 before zone 5 in match 5; booyahs in matches 1 and 2.
    Bravo: loses a player before zone 5 in every match.
    """
    rule, _ = ScoringRule.objects.get_or_create(name="Test rule", defaults={"placement_points": {}})
    season = Season.objects.create(name="S1", scoring_rule=rule)
    stage = Stage.objects.create(season=season, name="Scrims")
    day = MatchDay.objects.create(stage=stage, number=1, date=DAY, title="TDL DAY 15 8PM")
    alpha, bravo = Team.objects.create(name="Alpha"), Team.objects.create(name="Bravo Esports")
    charlie = Team.objects.create(name="Charlie")
    Team.objects.create(name="OUTPOST-33 ESPO")
    squads = {alpha: [player(1), player(2)], bravo: [player(3), player(4)], charlie: [player(5)]}
    entity = {p: 100 + p.game_uid for ps in squads.values() for p in ps}
    started = dt.datetime(2026, 10, 12, 19, 0, tzinfo=dt.UTC)
    for n in range(1, 6):
        match = Match.objects.create(
            match_day=day, number=n, status=Match.Status.PUBLISHED,
            started_at=started + dt.timedelta(minutes=25 * n),
        )  # fmt: skip
        for stage_index, at in enumerate([100, 300, 500, 700, ZONE5_AT, 1100], start=1):
            for state, t in (("PRE_SHRINK", at), ("SHRINK", at + 60)):
                ZonePhase.objects.create(
                    match=match, stage_index=stage_index, state=state, game_time_s=t,
                    outer_x=0, outer_z=0, inner_x=0, inner_z=0, inner_radius=100,
                )  # fmt: skip
        teams = [(alpha, 1 if n <= 2 else 3, 30), (bravo, 2 if n <= 2 else 1, 5)]
        if n == 1:
            teams.append((charlie, 3, 1))
        for team, place, points in teams:
            TeamMatchResult.objects.create(
                match=match, team=team, in_game_name=team.name, placement=place, kills=points // 3,
                placement_points=points, kill_points=0, total_points=points,
            )  # fmt: skip
            for p in squads[team]:
                PlayerMatchResult.objects.create(
                    match=match, player=p, team=team, raw_name=p.display_name,
                    display_name=p.display_name, entity_id=entity[p],
                )  # fmt: skip

        def kill(target, t, match=match):
            MatchEvent.objects.create(
                match=match, kind=K.KILL, source="DEBUGGER", game_time_s=t,
                target_entity=entity[target],
            )  # fmt: skip

        if n == 1:  # dies on the drop, respawns, lives
            kill(squads[alpha][0], 60.0)
            MatchEvent.objects.create(
                match=match, kind=K.RESPAWN, source="DEBUGGER", game_time_s=90.0,
                actor_entity=entity[squads[alpha][0]],
            )  # fmt: skip
        if n == 5:
            kill(squads[alpha][1], 800.0)
        kill(squads[bravo][0], 850.0)
        kill(squads[alpha][0], 1500.0)  # after zone 5: doesn't matter
    period = Period.objects.create(
        name="Weeks 41-42", starts_on=DAY, ends_on=DAY + dt.timedelta(days=13)
    )
    return {
        "season": season,
        "period": period,
        "alpha": alpha,
        "bravo": bravo,
        "charlie": charlie,
        "day": day,
    }


def task(league, rule, title, pp_done, pp_not_done=0, **params):
    t = Task.objects.create(
        period=league["period"], date=DAY, title=title, rule=rule, params=params,
        pp_done=pp_done, pp_not_done=pp_not_done,
    )  # fmt: skip
    check_task(t)
    return {r.team.name: r for r in t.results.select_related("team")}


def test_full_squad_alive_in_zone_5(league):
    res = task(
        league, Task.Rule.ZONE_ALIVE, "Full squad alive in zone 5", 1, -1, zone=5, min_matches=4
    )
    alpha, bravo = res["Alpha"], res["Bravo Esports"]
    assert (alpha.done, alpha.count, alpha.pp) == (True, 4, 1)
    assert alpha.detail == "Alive at zone 5 in 4 of 5"
    assert alpha.evidence[4]["ok"] is False and alpha.evidence[4]["note"] == "P2 down"
    assert (bravo.done, bravo.pp) == (False, -1)
    # Charlie played one match and was whole at zone 5: 1 of 1 is not 4.
    assert res["Charlie"].done is False


def test_booyahs_count_each(league):
    res = task(league, Task.Rule.BOOYAH, "Booyah", 2)
    assert (res["Alpha"].count, res["Alpha"].pp) == (2, 4)
    assert res["Bravo Esports"].pp == 6  # three booyahs
    assert res["Charlie"].pp == 0


def test_booyah_once(league):
    res = task(league, Task.Rule.BOOYAH, "Booyah", 2, once=True)
    assert res["Alpha"].pp == 2


def test_less_than_45_points(league):
    res = task(league, Task.Rule.DAY_POINTS, "Less than 45 total points", -1, op="lt", value=45)
    assert (res["Alpha"].done, res["Alpha"].pp) == (False, 0)  # 150 points
    assert (res["Bravo Esports"].done, res["Bravo Esports"].pp) == (True, -1)  # 25 points
    assert res["Bravo Esports"].detail == "25 points"


def test_placement_and_kills(league):
    res = task(league, Task.Rule.PLACEMENT, "Top 1 twice", 1, top=1, min_matches=3)
    assert res["Alpha"].done is False and res["Bravo Esports"].done is True
    res = task(league, Task.Rule.DAY_KILLS, "50 kills", 1, op="gte", value=50)
    assert res["Alpha"].done is True and res["Alpha"].detail == "50 kills"


def test_overrides_survive_rechecks_and_reuploads(league):
    res = task(league, Task.Rule.MANUAL, "On time", 1, -1)
    assert res["Alpha"].done is None and res["Alpha"].pp == 0
    row = res["Alpha"]
    row.override = True
    row.save()
    # A later upload moves the day's matches away, then back: the tick stays.
    Match.objects.update(status=Match.Status.DRAFT)
    refresh_season(league["season"])
    row.refresh_from_db()
    assert row.override is True and row.detail == "Didn't play"
    Match.objects.update(status=Match.Status.PUBLISHED)
    refresh_season(league["season"])
    row.refresh_from_db()
    assert row.matches and row.pp == 1


def test_table_starting_pp_and_text(league):
    found, missing = parse_table(OLD_TABLE)
    assert [(t.name, pp) for t, pp, _ in found] == [
        ("Alpha", 4), ("Bravo Esports", 2), ("Charlie", 0), ("OUTPOST-33 ESPO", -1)
    ]  # fmt: skip
    assert missing == ["NOBODY FC"]
    period = league["period"]
    for t, pp, _ in found:
        Adjustment.objects.create(period=period, team=t, kind="START", pp=pp)
    task(league, Task.Rule.BOOYAH, "Booyah", 2)
    hidden = Task.objects.create(
        period=period, date=DAY, title="Secret", rule="BOOYAH", pp_done=50, is_published=False
    )
    check_task(hidden)
    rows = table(period)
    assert [(r["team"].name, r["pp"]) for r in rows] == [
        ("Alpha", 8), ("Bravo Esports", 8), ("Charlie", 0), ("OUTPOST-33 ESPO", -1)
    ]  # fmt: skip

    with override_settings(PUBLIC_SITE=True):
        data = APIClient().get("/api/v1/pp").json()
    assert data["period"]["name"] == "Weeks 41-42"
    assert [t["title"] for t in data["tasks"]] == ["Booyah"]
    text = data["text"]
    assert "1. ALPHA — +8 PP" in text and "3. CHARLIE — 0 PP" in text
    assert "4. OUTPOST-33 ESPO — -1 PP" in text
    assert "📊 TOTAL: 4 TEAMS" in text and "🔴 1 team with negative PP" in text
    assert "🏆 BOOYAH\n→ +2 PP" in text

    with override_settings(PUBLIC_SITE=True):
        team = APIClient().get("/api/v1/pp/teams/alpha").json()
    assert team["pp"] == 8 and len(team["tasks"]) == 1
    assert team["tasks"][0]["result"]["detail"] == "2 booyahs"


@pytest.fixture
def staff():
    user = User.objects.create_user(email="staff@tdl.test", password="x")
    StaffProfile.objects.create(user=user, role=StaffProfile.Role.ANALYST)
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_staff_api(league, staff):
    resp = staff.post(
        "/api/v1/admin/pp/tasks",
        {"date": "2026-10-12", "title": "Full squad alive in zone 5 — in 4 out of 5 maps",
         "rule": "ZONE_ALIVE", "params": {"zone": 5, "min_matches": 4},
         "pp_done": 1, "pp_not_done": -1},
        format="json",
    )  # fmt: skip
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["period"] == league["period"].pk
    assert {r["team"]["name"]: r["pp"] for r in body["results"]}["Alpha"] == 1

    bad = staff.post("/api/v1/admin/pp/tasks", {"date": "2026-10-12", "title": "x",
                                               "rule": "DAY_POINTS",
                                               "params": {"op": "lt"}}, format="json")  # fmt: skip
    assert bad.status_code == 400
    later = {"date": "2027-01-01", "title": "x", "rule": "BOOYAH"}
    outside = staff.post("/api/v1/admin/pp/tasks", later, format="json")
    assert outside.status_code == 400 and "period" in outside.json()

    # Staff mark Bravo as done after all (the observer missed a match).
    bravo = league["bravo"]
    resp = staff.post("/api/v1/admin/pp/results",
                      {"task": body["id"], "team": bravo.pk, "override": True,
                       "note": "Observer missed M3"},
                      format="json")  # fmt: skip
    assert resp.json()["pp"] == 1 and resp.json()["done"] is True

    copied = staff.post(
        "/api/v1/admin/pp/tasks/copy", {"from": "2026-10-12", "to": "2026-10-13"}, format="json"
    )
    assert copied.status_code == 201 and copied.json()[0]["results"] == []  # no matches yet

    resp = staff.post(f"/api/v1/admin/pp/periods/{league['period'].pk}/starting",
                      {"text": OLD_TABLE, "dry_run": True}, format="json")  # fmt: skip
    assert resp.json()["missing"] == ["NOBODY FC"] and not Adjustment.objects.exists()
    staff.post(
        f"/api/v1/admin/pp/periods/{league['period'].pk}/starting",
        {"text": OLD_TABLE},
        format="json",
    )
    assert Adjustment.objects.filter(kind="START").count() == 4


def test_only_staff_manage(league):
    from apps.accounts.testing import signed_in_client

    assert signed_in_client().post("/api/v1/admin/pp/periods", {}).status_code == 403
    with override_settings(PUBLIC_SITE=False):
        assert APIClient().get("/api/v1/pp").status_code in (401, 403)
