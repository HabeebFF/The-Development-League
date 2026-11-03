"""Markets made automatically each scrim day."""

import datetime as dt

import pytest
from django.utils import timezone

from apps.accounts.models import StaffProfile
from apps.league.models import Match, MatchDay, Player, ScoringRule, Season, Stage, Team
from apps.predictions import auto
from apps.predictions.models import AutoMarket, AutoSettings, Fixture, Market
from apps.results.models import MatchEvent, PlayerMatchResult, TeamMatchResult

from .test_settlement import as_user, make_user

pytestmark = pytest.mark.django_db
C, S = Market.Category, Market.Status

EIGHT = ["Alpha", "Bravo", "Charlie", "Delta"]
TEN = ["Echo", "Foxtrot", "Golf", "Hotel"]


@pytest.fixture(autouse=True)
def _on(settings):
    settings.PREDICTIONS_ENABLED = True


@pytest.fixture
def staff():
    user = make_user("staff@tdl.test")
    StaffProfile.objects.create(user=user)
    return user


def next_weekday(weekday: int) -> dt.date:
    """The next given weekday (0 = Monday) at least two days ahead."""
    day = auto.today() + dt.timedelta(days=2)
    return day + dt.timedelta(days=(weekday - day.weekday()) % 7)


@pytest.fixture
def lg():
    """Two published sessions a week ago: 8PM with EIGHT, 10PM with TEN, 3 matches each."""
    rule = ScoringRule.objects.create(name="R", placement_points={"1": 12, "2": 9, "3": 8, "4": 7})
    season = Season.objects.create(name="S", slug="s", scoring_rule=rule, is_active=True)
    stage = Stage.objects.create(season=season, name="Scrims")
    teams = {n: Team.objects.create(name=n) for n in EIGHT + TEN + ["Idle"]}
    played = auto.today() - dt.timedelta(days=7)
    uid = 1000
    for number, (hour, names) in enumerate((("8PM", EIGHT), ("10PM", TEN)), start=1):
        day = MatchDay.objects.create(
            stage=stage, number=number, date=played, title=f"TDL DAY 9 {hour}"
        )
        players = {}
        for name in names:
            for i in range(2):
                uid += 1
                players[(name, i)] = Player.objects.create(
                    game_uid=uid, current_name_raw=f"{name}{i}", display_name=f"{name}{i}",
                    search_name=f"{name}{i}".lower(), current_team=teams[name],
                )  # fmt: skip
        for m in range(1, 4):
            match = Match.objects.create(
                match_day=day, number=m, status=Match.Status.PUBLISHED,
                started_at=timezone.now() - dt.timedelta(days=7, minutes=30 * (10 - m)),
            )  # fmt: skip
            MatchEvent.objects.create(
                match=match, source=MatchEvent.Source.REPLAY_INFO, kind=MatchEvent.Kind.KILL,
                game_time_s=30 + m, actor_team=teams[names[m % 4]],
                target_team=teams[names[(m + 1) % 4]],
            )  # fmt: skip
            for place, name in enumerate(names, start=1):
                kills = 10 - 2 * place + m
                TeamMatchResult.objects.create(
                    match=match, team=teams[name], in_game_name=name, placement=place,
                    kills=kills, placement_points=0, kill_points=kills,
                    total_points=13 - place + kills,
                )  # fmt: skip
                for i in range(2):
                    p = players[(name, i)]
                    PlayerMatchResult.objects.create(
                        match=match, player=p, team=teams[name], raw_name=p.display_name,
                        display_name=p.display_name, kills=kills // 2 + i,
                    )  # fmt: skip
    return {"season": season, "teams": teams}


def made(date, session=None):
    qs = (
        Market.objects.filter(fixture__date=date)
        if session is None
        else Market.objects.filter(fixture__date=date, fixture__session=session)
    )
    return qs


def test_a_scrim_day_gets_both_sessions_with_open_markets(lg):
    date = next_weekday(2)  # a Wednesday: no weekly market
    report = auto.run(date)
    assert report["notes"] == [], report
    for session, names in (("8PM", EIGHT), ("10PM", TEN)):
        whole = Fixture.objects.get(date=date, session=session, match_number=None)
        assert sorted(whole.teams.values_list("name", flat=True)) == names
        assert Fixture.objects.filter(date=date, session=session).count() == 6
        markets = made(date, session)
        cats = sorted(markets.values_list("category", flat=True))
        assert cats.count(C.BOOYAH) == 5 and cats.count(C.TOTAL_KILLS) == 5
        assert cats.count(C.FIRST_BLOOD) == 5 and cats.count(C.SESSION_H2H) == 2
        assert {C.SESSION_WINNER, C.MOST_BOOYAHS, C.SESSION_FRAGGER} <= set(cats)
        # Every match: first team out, top fragger, top 3 and finishing position per team,
        # kills lines for the 4 teams and 5 players with the most kills, 2 handicaps.
        for cat, each in (
            (C.FIRST_OUT, 1), (C.TOP_FRAGGER, 1), (C.TOP_N, 4), (C.FINISH_BAND, 4),
            (C.TEAM_KILLS, 4), (C.KILLS_HANDICAP, 2), (C.PLAYER_KILLS, 5),
        ):  # fmt: skip
            assert cats.count(cat) == 5 * each, cat
        assert markets.count() == 5 * 24 + 5
        start = auto.session_start(date, session)
        for m in markets:
            assert m.status == S.OPEN and m.closes_at == start
            assert m.created_by.email == auto.SYSTEM_EMAIL
        booyah = markets.filter(category=C.BOOYAH).first()
        assert sorted(booyah.outcomes.values_list("team__name", flat=True)) == names
        assert all(o.odds > 1 for o in booyah.outcomes.all())
    # Lines sit near each side's recent average, and handicaps give the stronger side less.
    m1 = made(date, "8PM").filter(fixture__match_number=1)
    alpha = m1.get(category=C.TEAM_KILLS, params__team=lg["teams"]["Alpha"].pk)
    assert alpha.params["line"] == 10  # Alpha averaged 10 kills (8 + 1..3)
    for h in m1.filter(category=C.KILLS_HANDICAP):
        a, b = h.params["teams"]
        assert h.params["line"] >= 1
        assert h.outcomes.get(team_id=a).label.endswith(f"-{h.params['line'] - 0.5:g} kills")
    star = m1.filter(category=C.PLAYER_KILLS).first()
    assert star.params["line"] >= 1 and star.outcomes.count() == 2
    # The two head-to-heads never share a team.
    h2h = made(date, "8PM").filter(category=C.SESSION_H2H)
    ids = [t for m in h2h for t in m.params["teams"]]
    assert len(ids) == len(set(ids)) == 4
    assert not Market.objects.filter(category=C.RANGE_WINNER).exists()
    assert not auto.system_user().is_active


def test_running_again_makes_nothing_new_and_keeps_deleted_ones_deleted(lg, staff):
    date = next_weekday(2)
    auto.run(date)
    count = Market.objects.count()
    gone = made(date, "8PM").get(title="Booyah · Match 3")
    gone.delete()
    again = auto.run(date)
    assert again["made"] == []
    assert Market.objects.count() == count - 1
    assert AutoMarket.objects.filter(market__isnull=True).count() == 1


def test_staff_edits_and_their_own_lobby_are_kept(lg, staff):
    date = next_weekday(2)
    whole = Fixture.objects.create(
        season=lg["season"], date=date, session="8PM",
        scheduled_at=auto.session_start(date, "8PM"),
    )  # fmt: skip
    whole.teams.set([lg["teams"][n] for n in ("Alpha", "Bravo", "Idle")])
    auto.run(date)
    booyah = made(date, "8PM").get(title="Booyah · Match 1")
    assert sorted(booyah.outcomes.values_list("team__name", flat=True)) == [
        "Alpha",
        "Bravo",
        "Idle",
    ]


def test_changing_the_lobby_remakes_markets_nobody_predicted_on(lg, staff):
    from .test_player_rules import bet

    date = next_weekday(2)
    auto.run(date)
    whole = Fixture.objects.get(date=date, session="8PM", match_number=None)
    taken = made(date, "8PM").get(title="Booyah · Match 1")
    bet(make_user("fan@tdl.test"), taken)
    new = [lg["teams"][n].pk for n in ("Alpha", "Bravo", "Idle")]
    res = as_user(staff).patch(
        f"/api/v1/admin/predictions/fixtures/{whole.pk}", {"teams": new}, format="json"
    )
    assert res.status_code == 200, res.content
    # The market with a prediction stays as it was; the rest now list the new lobby.
    assert Market.objects.filter(pk=taken.pk).exists()
    assert taken.outcomes.count() == 4
    m2 = made(date, "8PM").get(title="Booyah · Match 2")
    assert sorted(m2.outcomes.values_list("team_id", flat=True)) == sorted(new)
    assert made(date, "8PM").filter(title="Booyah · Match 1").count() == 1
    # 10PM is left alone.
    assert made(date, "10PM").filter(category=C.BOOYAH).count() == 5


def test_switch_days_and_nights_off(lg, settings):
    date = next_weekday(2)
    conf = AutoSettings.get()
    conf.skip_dates = [date.isoformat()]
    conf.save()
    assert auto.run(date)["made"] == []
    conf.skip_dates, conf.weekdays = [], [0, 1]
    conf.save()
    assert auto.run(date)["made"] == []
    conf.weekdays, conf.enabled = list(range(7)), False
    conf.save()
    assert auto.run(date)["made"] == []
    conf.enabled = True
    conf.save()
    settings.PREDICTIONS_ENABLED = False
    assert auto.run(date)["made"] == []
    assert not Market.objects.exists()
    # The staff button makes them anyway.
    assert auto.run(date, force=True)["made"]


def test_mondays_add_the_weekly_market(lg):
    date = next_weekday(0)
    auto.run(date)
    week = Market.objects.get(category=C.RANGE_WINNER)
    assert week.fixture is None and week.status == S.OPEN
    assert week.params["from"] == date.isoformat()
    assert week.params["to"] == (date + dt.timedelta(days=6)).isoformat()
    assert len(week.params["teams"]) == 8
    assert "Idle" not in week.outcomes.values_list("team__name", flat=True)


def test_a_market_without_odds_is_noted_once(lg):
    MatchEvent.objects.all().delete()  # no timed kills: no first-blood odds
    report = auto.run(next_weekday(2))
    notes = [n for n in report["notes"] if n.startswith("First blood")]
    assert len(notes) == 1, report["notes"]
    assert not Market.objects.filter(category=C.FIRST_BLOOD).exists()
    assert Market.objects.filter(category=C.BOOYAH).count() == 10


def test_no_earlier_session_means_a_note_not_a_guess(lg):
    MatchDay.objects.filter(title__endswith="10PM").update(title="TDL DAY 9 9PM")
    report = auto.run(next_weekday(2))
    assert any(n.startswith("10PM: no earlier 10PM session") for n in report["notes"])
    assert not Market.objects.filter(fixture__session="10PM").exists()
    assert Market.objects.filter(fixture__session="8PM").exists()


def test_staff_settings_and_run_now(lg, staff):
    client = as_user(staff)
    res = client.patch(
        "/api/v1/admin/predictions/auto",
        {"weekdays": [4, 5, 5], "skip_dates": ["2001-01-01", next_weekday(2).isoformat()]},
        format="json",
    )
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["weekdays"] == [4, 5]
    assert body["skip_dates"] == [next_weekday(2).isoformat()]  # past dates dropped
    assert (
        client.patch("/api/v1/admin/predictions/auto", {"weekdays": [9]}, format="json").status_code
        == 400
    )
    date = next_weekday(2).isoformat()
    run = client.post("/api/v1/admin/predictions/auto/run", {"date": date}, format="json")
    assert run.status_code == 200 and run.json()["made"]
    assert client.get("/api/v1/admin/predictions/auto").json()["last_report"]["date"] == date
    old = client.post("/api/v1/admin/predictions/auto/run", {"date": "2001-01-01"}, format="json")
    assert old.status_code == 400
    fan = as_user(make_user("fan@tdl.test"))
    assert fan.get("/api/v1/admin/predictions/auto").status_code == 403


def test_the_hourly_task_waits_for_ten(lg, monkeypatch):
    date = auto.today()
    nine = dt.datetime.combine(date, dt.time(9, 5), tzinfo=auto.local_tz())
    monkeypatch.setattr(auto.timezone, "now", lambda: nine)
    assert auto.run()["notes"] == ["Too early."]
    eleven = dt.datetime.combine(date, dt.time(11, 5), tzinfo=auto.local_tz())
    monkeypatch.setattr(auto.timezone, "now", lambda: eleven)
    assert auto.run()["made"]
