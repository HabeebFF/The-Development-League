"""Tournament mode: own standings, moving match days in, prizes, payouts and held prizes."""

import datetime as dt

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import StaffProfile, User
from apps.league.models import Match, MatchDay, Player, ScoringRule, Season, Stage, Team
from apps.predictions.models import LedgerEntry
from apps.predictions.services import wallet_for
from apps.results import ratings
from apps.results.models import PlayerMatchResult, StandingRow, TeamMatchResult
from apps.results.standings import rebuild_season
from apps.tournaments import services
from apps.tournaments.models import PrizePayout, Tournament

pytestmark = pytest.mark.django_db
NAMES = [f"T{i:02d}" for i in range(1, 15)]  # 14 league teams
PASSWORD = "a-Long-password-42"


def user(email, staff=False) -> User:
    u = User.objects.create_user(email=email, password=PASSWORD, display_name=email[:6])
    if staff:
        StaffProfile.objects.create(user=u)
    return u


def client(u) -> APIClient:
    c = APIClient()
    c.force_authenticate(u)
    return c


@pytest.fixture
def lg():
    """A league season where T01 leads and T14 is last, with 2 players a team."""
    rule = ScoringRule.objects.create(
        name="R", placement_points={str(i): 15 - i for i in range(1, 15)}
    )
    season = Season.objects.create(name="League", slug="league", scoring_rule=rule, is_active=True)
    stage = Stage.objects.create(season=season, name="Scrims")
    teams = {n: Team.objects.create(name=n) for n in NAMES}
    players = {}
    uid = 100
    for n in NAMES:
        for i in range(2):
            uid += 1
            players[(n, i)] = Player.objects.create(
                game_uid=uid, current_name_raw=f"{n}p{i}", display_name=f"{n}p{i}",
                search_name=f"{n}p{i}".lower(), current_team=teams[n],
            )  # fmt: skip
    day = MatchDay.objects.create(
        stage=stage, number=1, title="TDL DAY 1 10PM", date=dt.date(2026, 11, 1)
    )
    play(day, 1, NAMES, players, teams)
    rebuild_season(season)
    return {"season": season, "stage": stage, "teams": teams, "players": players}


def play(day, number, order, players, teams, kills=None):
    """One published match; ``order`` is the finishing order; player 0 gets the kills."""
    match = Match.objects.create(match_day=day, number=number, status=Match.Status.PUBLISHED)
    for place, name in enumerate(order, start=1):
        k = (kills or {}).get(name, 15 - place)
        TeamMatchResult.objects.create(
            match=match, team=teams[name], in_game_name=name, placement=place, kills=k,
            placement_points=15 - place, kill_points=k, total_points=15 - place + k,
        )  # fmt: skip
        for i in range(2):
            p = players[(name, i)]
            PlayerMatchResult.objects.create(
                match=match, player=p, team=teams[name], raw_name=p.display_name,
                display_name=p.display_name, kills=k if i == 0 else 0,
            )  # fmt: skip
    return match


@pytest.fixture
def cup(lg):
    t = services.create_tournament("TDL Cup 2026", keyword="CUP", planned_matches=2)
    t.teams.set(services.top_teams(12))
    return t


def cup_night(lg, cup, order=None):
    stage = services.final_stage(cup)
    day = MatchDay.objects.create(stage=stage, number=1, title="TDL CUP DAY 1 10PM")
    top12 = NAMES[:12]
    for n in (1, 2):
        play(day, n, order or top12, lg["players"], lg["teams"])
    rebuild_season(cup.season)
    ratings.refresh()
    return day


def test_a_tournament_has_its_own_season_and_stays_out_of_scrim_standings(lg, cup):
    assert cup.season != lg["season"] and cup.season.tournament == cup
    assert services.scrim_season() == lg["season"]
    assert [t.name for t in cup.teams.order_by("name")] == NAMES[:12]  # the top 12 invited
    cup_night(lg, cup, order=list(reversed(NAMES[:12])))
    league = StandingRow.objects.get(season=lg["season"], scope="season", rank=1)
    assert league.team.name == "T01" and league.matches_played == 1  # cup matches not added
    top = StandingRow.objects.get(season=cup.season, scope="season", rank=1)
    assert top.team.name == "T12" and top.matches_played == 2


def test_moving_match_days_in_rebuilds_both_tables(lg, cup):
    day = MatchDay.objects.create(
        stage=lg["stage"], number=2, title="TDL CUP DAY 1 10PM", date=dt.date(2026, 11, 16)
    )
    play(day, 1, list(reversed(NAMES)), lg["players"], lg["teams"])
    rebuild_season(lg["season"])
    assert (
        StandingRow.objects.get(
            season=lg["season"], scope="season", team__name="T01"
        ).matches_played
        == 2
    )
    services.move_days(cup, [day.pk])
    day.refresh_from_db()
    assert day.stage.season == cup.season
    assert (
        StandingRow.objects.get(
            season=lg["season"], scope="season", team__name="T01"
        ).matches_played
        == 1
    )
    assert StandingRow.objects.get(season=cup.season, scope="season", rank=1).team.name == "T14"


def test_split_adds_up_exactly():
    from collections import Counter

    shares = services.split(125000, Counter({1: 2, 2: 2, 3: 1, 4: 2}))
    assert sum(shares.values()) == 125000
    assert shares == {1: 31250, 2: 31250, 4: 31250, 3: 31250}
    odd = services.split(100, Counter({1: 1, 2: 3, 3: 1}))
    assert sum(odd.values()) == 100 and odd[2] == 34


def test_default_prizes_add_up():
    from apps.tournaments.models import default_prizes

    assert services.total_dc(default_prizes()) == 1_000_000
    assert services.total_cash(default_prizes()) == 100_000


def test_payout_pays_accounts_and_holds_the_rest(lg, cup):
    cup_night(lg, cup)
    staff = user("staff@tdl.test", staff=True)
    p0 = lg["players"][("T01", 0)]
    p0.user = user("t01p0@tdl.test")
    p0.save()
    view = services.preview(cup)
    assert view["total_dc"] == 950_000  # no Best IGL yet
    with pytest.raises(services.TournamentError, match="Best IGL"):
        services.confirm(cup, staff)
    cup.best_igl = lg["players"][("T03", 0)]
    cup.save()
    view = services.preview(cup)
    assert view["ready"] and view["total_dc"] == 1_000_000
    first = next(p for p in view["prizes"] if p["key"] == "place:1")
    assert first["winners"][0]["team"]["name"] == "T01"
    assert [s["amount"] for s in first["winners"][0]["shares"]] == [150000, 150000]
    kills = next(p for p in view["prizes"] if p["key"] == "top_kills")
    assert kills["winners"][0]["player"] == "T01p0"

    result = services.confirm(cup, staff)
    assert result["payouts"] > 0 and result["paid"] >= 1
    paid = PrizePayout.objects.filter(player=p0, paid_at__isnull=False)
    assert paid.exists()
    assert wallet_for(p0.user).balance == 1000 + sum(p.amount for p in paid)
    assert (
        sum(PrizePayout.objects.filter(tournament=cup).values_list("amount", flat=True))
        == 1_000_000
    )
    with pytest.raises(services.TournamentError):
        services.confirm(cup, staff)  # only once

    # A held prize lands when the winner's game UID is linked to an account.
    p1 = lg["players"][("T01", 1)]
    assert PrizePayout.objects.filter(player=p1, paid_at__isnull=True).exists()
    p1.user = user("t01p1@tdl.test")
    p1.save()
    services.pay_held(p1.pk)  # on_commit doesn't run inside the test transaction
    assert not PrizePayout.objects.filter(player=p1, paid_at__isnull=True).exists()
    assert wallet_for(p1.user).balance == 1000 + 150000
    assert LedgerEntry.objects.filter(idempotency_key__startswith="tournament-prize:").count() >= 2


def test_payout_waits_for_every_match(lg, cup):
    cup.planned_matches = 3
    cup.best_igl = lg["players"][("T01", 1)]
    cup.save()
    cup_night(lg, cup)
    staff = user("staff@tdl.test", staff=True)
    with pytest.raises(services.TournamentError, match="Only 2 of 3"):
        services.confirm(cup, staff)


def test_staff_api_and_public_page(lg):
    staff = client(user("staff@tdl.test", staff=True))
    res = staff.post(
        "/api/v1/admin/tournaments",
        {"name": "TDL Cup 2026", "keyword": "CUP", "planned_matches": 12,
         "starts_on": "2026-11-16", "ends_on": "2026-11-17"},
        format="json",
    )  # fmt: skip
    assert res.status_code == 201, res.content
    slug = res.json()["slug"]
    assert res.json()["total_dc"] == 1_000_000
    res = staff.post(f"/api/v1/admin/tournaments/{slug}/invite-top", {}, format="json")
    assert len(res.json()["teams"]) == 12
    bad = staff.patch(
        f"/api/v1/admin/tournaments/{slug}", {"prizes": [{"key": "place:x"}]}, format="json"
    )
    assert bad.status_code == 400
    ok = staff.patch(
        f"/api/v1/admin/tournaments/{slug}", {"cash_paid": ["place:1", "nope"]}, format="json"
    )
    assert ok.json()["prizes"][0]["cash_paid"] is True
    fan = client(user("fan@tdl.test"))
    assert fan.get(f"/api/v1/admin/tournaments/{slug}").status_code == 403
    page = APIClient().get(f"/api/v1/tournaments/{slug}")
    assert page.status_code == 200 and page.json()["status"] in ("upcoming", "live")
    assert APIClient().get("/api/v1/tournaments").json()[0]["slug"] == slug
    assert APIClient().get(f"/api/v1/tournaments/{slug}/players").status_code == 200
    payout = staff.post(f"/api/v1/admin/tournaments/{slug}/payout", {}, format="json")
    assert payout.status_code == 400  # no matches yet


def test_predictions_link_a_cup_night_from_the_tournament_season(lg, cup):
    from apps.predictions import autosettle
    from apps.predictions.models import Fixture

    date = dt.date(2026, 11, 16)
    fixture = Fixture.objects.create(
        season=lg["season"], date=date, session="10PM", match_number=1,
        scheduled_at=dt.datetime(2026, 11, 16, 21, tzinfo=dt.UTC),
    )  # fmt: skip
    day = MatchDay.objects.create(
        stage=services.final_stage(cup), number=1, title="TDL CUP DAY 1 10PM", date=date
    )
    match = play(day, 1, NAMES[:12], lg["players"], lg["teams"])
    autosettle.link_match(match)
    fixture.refresh_from_db()
    assert fixture.match == match
    assert Tournament.objects.get(pk=cup.pk).season.tournament == cup


def test_staff_can_add_remove_and_swap_teams(lg, cup):
    staff = client(user("staff@tdl.test", staff=True))
    url = f"/api/v1/admin/tournaments/{cup.slug}"
    ids = list(cup.teams.order_by("name").values_list("pk", flat=True))
    t13, t14 = lg["teams"]["T13"].pk, lg["teams"]["T14"].pk
    res = staff.patch(url, {"teams": [*ids[1:], t13]}, format="json")  # swap T01 for T13
    names = [x["name"] for x in res.json()["teams"]]
    assert "T01" not in names and "T13" in names and len(names) == 12
    res = staff.patch(url, {"teams": [*ids[1:], t13, t14]}, format="json")  # add one
    assert len(res.json()["teams"]) == 13
    assert staff.patch(url, {"teams": [999999]}, format="json").status_code == 400
    cup.confirmed_at = dt.datetime(2026, 11, 18, tzinfo=dt.UTC)
    cup.save()
    assert staff.patch(url, {"teams": ids}, format="json").status_code == 400
