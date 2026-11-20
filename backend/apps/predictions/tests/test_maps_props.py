"""Map-aware markets and the new player markets (Habeeb, 2026-11-20): each match's map is
drawn when sign-up opens, match markets are named and priced for it, and a match played on
another map is refunded. Players get knocks and damage over/unders each match and deaths
over the session."""

# ruff: noqa: F811  (pytest fixtures imported from other test files)

import datetime as dt

import pytest
from django.utils import timezone

from apps.league.models import Match, MatchDay, Player
from apps.maps.models import Map
from apps.predictions import auto
from apps.predictions.markets import MarketError, clean_params, create_market, transition
from apps.predictions.models import Fixture, Market
from apps.predictions.odds import suggest_odds
from apps.predictions.settlement import suggest
from apps.results.models import PlayerMatchResult, TeamMatchResult
from apps.scrims import maps as mp
from apps.scrims.models import ScrimSession

from .test_auto import lg as _lg  # noqa: F401
from .test_auto import made
from .test_odds import _margin, ids, league  # noqa: F401  (fixtures)
from .test_scrim_lobby import _on, lg, night, sign_up, staff  # noqa: F401  (fixtures)

pytestmark = pytest.mark.django_db
C, S = Market.Category, Market.Status


def by_name(name):
    return Map.objects.get(name=name)


# -- markets follow the drawn maps -----------------------------------------------------------------


def test_match_markets_are_named_and_priced_for_their_map(lg, night, staff):
    date, at = night
    sign_up(date, "8PM", [lg["teams"][n] for n in ("Alpha", "Golf", "Idle")], staff)
    drawn = mp.ensure(ScrimSession.objects.get(date=date, session="8PM"))
    assert len(drawn) == 5
    at(18, 1)
    auto.run(date, force=True)
    names = dict(Map.objects.values_list("pk", "name"))
    for n in range(1, 6):
        f = Fixture.objects.get(date=date, session="8PM", match_number=n)
        assert f.map_id == drawn[n - 1]
        booyah = made(date, "8PM").get(fixture=f, category=C.BOOYAH)
        assert booyah.title == f"Booyah · Match {n} · {names[drawn[n - 1]]}"
        assert booyah.map_id == drawn[n - 1]
        assert set(made(date, "8PM").filter(fixture=f).values_list("map", flat=True)) == {
            drawn[n - 1]
        }
    # Session markets aren't about one map.
    assert not made(date, "8PM").filter(fixture__match_number=None, map__isnull=False).exists()


def test_staff_changing_maps_remakes_markets_nobody_predicted_on(
    lg, night, staff, django_capture_on_commit_callbacks
):
    from .test_player_rules import bet
    from .test_settlement import make_user

    date, at = night
    sign_up(date, "8PM", [lg["teams"][n] for n in ("Alpha", "Golf", "Idle")], staff)
    scrim = ScrimSession.objects.get(date=date, session="8PM")
    mp.ensure(scrim)
    at(18, 1)
    auto.run(date, force=True)
    first = Fixture.objects.get(date=date, session="8PM", match_number=1)
    taken = made(date, "8PM").get(fixture=first, category=C.BOOYAH)
    bet(make_user("fan@tdl.test"), taken)
    kalahari, bermuda = by_name("Kalahari").pk, by_name("Bermuda").pk
    chosen = [kalahari, bermuda, kalahari, bermuda, kalahari]
    if scrim.maps[0] == kalahari:
        chosen = [bermuda, kalahari, bermuda, kalahari, bermuda]
    with django_capture_on_commit_callbacks(execute=True):
        mp.set_maps(scrim, chosen, staff)
    first.refresh_from_db()
    assert first.map_id == chosen[0]
    # The market with a prediction keeps the map it was priced for...
    taken.refresh_from_db()
    assert taken.map_id != chosen[0] and taken.status == S.OPEN
    # ...the others were made again for the new map.
    total = made(date, "8PM").get(fixture=first, category=C.TOTAL_KILLS)
    assert total.map_id == chosen[0] and total.title.endswith(Map.objects.get(pk=chosen[0]).name)
    m2 = Fixture.objects.get(date=date, session="8PM", match_number=2)
    assert made(date, "8PM").get(fixture=m2, category=C.BOOYAH).map_id == chosen[1]


# -- wrong map played ------------------------------------------------------------------------------


def played_on(lg, fixture, map_obj):
    """Upload the fixture's match, played on ``map_obj``."""
    day = MatchDay.objects.filter(stage__season=lg["season"]).first()
    match = Match.objects.create(
        match_day=day, number=99, status=Match.Status.PUBLISHED, map=map_obj,
        started_at=timezone.now(),
    )  # fmt: skip
    teams = list(fixture.teams.all()) or list(lg["teams"].values())[:3]
    for place, team in enumerate(teams[:3], start=1):
        TeamMatchResult.objects.create(
            match=match, team=team, in_game_name=team.name, placement=place, kills=3,
            placement_points=0, kill_points=3, total_points=3,
        )  # fmt: skip
    fixture.match = match
    fixture.save(update_fields=["match"])
    return match


@pytest.fixture
def market_on_kalahari(lg, staff):
    fixture = Fixture.objects.create(
        season=lg["season"], date=dt.date(2026, 11, 30), session="8PM", match_number=1,
        scheduled_at=timezone.now() + dt.timedelta(hours=1), map=by_name("Kalahari"),
    )  # fmt: skip
    teams = [lg["teams"][n].pk for n in ("Alpha", "Bravo", "Charlie")]
    m = create_market(
        actor=staff, category=C.BOOYAH, title="Booyah", season=lg["season"], fixture=fixture,
        params={"teams": teams}, odds={f"team:{t}": "3.00" for t in teams},
        opens_at=timezone.now(), closes_at=timezone.now() + dt.timedelta(hours=1),
    )  # fmt: skip
    return transition(m, S.OPEN, actor=staff)


def test_a_match_played_on_another_map_is_refunded(lg, market_on_kalahari):
    m = market_on_kalahari
    assert m.map.name == "Kalahari"
    played_on(lg, m.fixture, by_name("Bermuda"))
    result = suggest(m)
    assert result["kind"] == "VOID"
    assert "Kalahari but Bermuda was played" in result["note"]


def test_the_right_map_settles_as_usual(lg, market_on_kalahari):
    played_on(lg, market_on_kalahari.fixture, by_name("Kalahari"))
    assert suggest(market_on_kalahari)["kind"] == "SETTLE"


def test_an_unknown_map_settles_as_usual(lg, market_on_kalahari):
    played_on(lg, market_on_kalahari.fixture, None)
    assert suggest(market_on_kalahari)["kind"] == "SETTLE"


# -- map-aware odds --------------------------------------------------------------------------------


def test_a_team_strong_on_a_map_is_favoured_there(league):
    """T12, the worst team, won every one of its Kalahari matches."""
    kalahari = by_name("Kalahari")
    t12 = league["teams"][11]
    matches = list(Match.objects.filter(match_day__in=league["days"]).order_by("pk"))
    for match in matches[::2]:
        match.map = kalahari
        match.save(update_fields=["map"])
        rows = list(TeamMatchResult.objects.filter(match=match).order_by("placement"))
        mine = next(r for r in rows if r.team_id == t12.pk)
        for r in rows:
            if r.placement < mine.placement:
                r.placement += 1
                r.save(update_fields=["placement"])
        mine.placement = 1
        mine.save(update_fields=["placement"])

    def chance(map_obj):
        f = Fixture.objects.create(
            season=league["season"], date=dt.date(2026, 10, 20), session="8PM",
            match_number=1 if map_obj else 2, map=map_obj,
            scheduled_at=dt.datetime(2026, 10, 20, 19, tzinfo=dt.UTC),
        )  # fmt: skip
        result = suggest_odds(
            season=league["season"], category=C.TOP_N, params={"team": t12.pk, "n": 3},
            fixture=f,
        )  # fmt: skip
        return result

    on_kalahari, anywhere = chance(kalahari), chance(None)
    assert on_kalahari["map"] == "Kalahari" and anywhere["map"] is None
    assert on_kalahari["chances"]["yes"] > anywhere["chances"]["yes"] + 0.15


def test_session_markets_price_each_drawn_map(league):
    kalahari = by_name("Kalahari")
    f = Fixture.objects.create(
        season=league["season"], date=dt.date(2026, 10, 20), session="8PM",
        scheduled_at=dt.datetime(2026, 10, 20, 19, tzinfo=dt.UTC),
    )  # fmt: skip
    ScrimSession.objects.create(date=f.date, session="8PM", max_teams=12, maps=[kalahari.pk] * 6)
    result = suggest_odds(
        season=league["season"], category=C.SESSION_WINNER,
        params={"teams": ids(league, 1, 2, 3)}, fixture=f,
    )  # fmt: skip
    assert result["matches"] == 6 and result["maps"] == ["Kalahari"] * 6


# -- new player markets ----------------------------------------------------------------------------


@pytest.fixture
def stats(lg):
    """Alpha0 got 2-4 knocks, 600-1000 damage and died once in each of last week's matches."""
    player = Player.objects.get(display_name="Alpha0")
    for n, row in enumerate(PlayerMatchResult.objects.filter(player=player).order_by("pk")):
        row.knocks, row.damage_dealt, row.deaths = 2 + n, 600 + 200 * n, 1
        row.save(update_fields=["knocks", "damage_dealt", "deaths"])
    return player


def test_new_lines_are_checked(lg, stats):
    assert clean_params(C.PLAYER_KNOCKS, {"player": stats.pk, "line": 2}) == {
        "player": stats.pk,
        "line": 2,
    }
    with pytest.raises(MarketError, match="knocks line"):
        clean_params(C.PLAYER_KNOCKS, {"player": stats.pk, "line": 0})
    with pytest.raises(MarketError, match="deaths line"):
        clean_params(C.SESSION_DEATHS, {"player": stats.pk, "line": 99})


def test_knocks_and_deaths_odds(lg, stats):
    session = Fixture.objects.create(
        season=lg["season"], date=dt.date(2026, 11, 30), session="8PM",
        scheduled_at=timezone.now() + dt.timedelta(hours=1),
    )  # fmt: skip
    match = Fixture.objects.create(
        season=lg["season"], date=session.date, session="8PM", match_number=1,
        scheduled_at=session.scheduled_at,
    )  # fmt: skip
    easy = suggest_odds(
        season=lg["season"], category=C.PLAYER_KNOCKS, params={"player": stats.pk, "line": 2},
        fixture=match,
    )  # fmt: skip
    hard = suggest_odds(
        season=lg["season"], category=C.PLAYER_KNOCKS, params={"player": stats.pk, "line": 4},
        fixture=match,
    )  # fmt: skip
    assert easy["chances"]["yes"] > hard["chances"]["yes"]
    with pytest.raises(MarketError, match="whole-session"):
        suggest_odds(
            season=lg["season"], category=C.SESSION_DEATHS,
            params={"player": stats.pk, "line": 3}, fixture=match,
        )  # fmt: skip
    deaths = suggest_odds(
        season=lg["season"], category=C.SESSION_DEATHS,
        params={"player": stats.pk, "line": 3}, fixture=session,
    )  # fmt: skip
    assert deaths["chances"]["yes"] > 0.5  # dies about once a match, 3+ in a session


def test_auto_markets_add_knocks_damage_and_deaths(lg, night, staff, stats):
    date, at = night
    sign_up(date, "8PM", [lg["teams"][n] for n in ("Alpha", "Golf", "Idle")], staff)
    at(18, 1)
    auto.run(date, force=True)
    mine = made(date, "8PM").filter(params__player=stats.pk)
    first = mine.filter(fixture__match_number=1)
    knocks = first.get(category=C.PLAYER_KNOCKS)
    assert knocks.params["line"] == 3 and knocks.title.startswith("Alpha0 knocks · Match 1")
    assert first.get(category=C.PLAYER_DAMAGE).params["line"] == 800
    deaths = mine.get(category=C.SESSION_DEATHS)
    assert deaths.fixture.match_number is None
    assert deaths.params["line"] == 5 and deaths.title == "Alpha0 deaths (8PM)"
    labels = list(deaths.outcomes.values_list("label", flat=True))
    assert labels == ["Alpha0: over 4.5 deaths", "Alpha0: under 4.5 deaths"]


def _player_market(lg, staff, category, player, line, fixture):
    m = create_market(
        actor=staff, category=category, title="t", season=lg["season"], fixture=fixture,
        params={"player": player.pk, "line": line}, odds={"yes": "1.90", "no": "1.90"},
        opens_at=timezone.now(), closes_at=timezone.now() + dt.timedelta(hours=1),
    )  # fmt: skip
    return transition(m, S.OPEN, actor=staff)


def test_knocks_settle_and_missing_figures_refund(lg, staff, stats):
    last = PlayerMatchResult.objects.filter(player=stats).order_by("pk").last()
    fixture = Fixture.objects.create(
        season=lg["season"], date=dt.date(2026, 11, 30), session="8PM", match_number=1,
        scheduled_at=timezone.now(), match=last.match,
    )  # fmt: skip
    m = _player_market(lg, staff, C.PLAYER_KNOCKS, stats, 4, fixture)
    result = suggest(m)
    assert result["kind"] == "SETTLE" and result["note"] == "4 knocks."
    assert m.outcomes.get(pk=result["winners"][0]).code == "yes"
    last.knocks = None
    last.save(update_fields=["knocks"])
    result = suggest(m)
    assert result["kind"] == "VOID" and "no knocks figures" in result["note"]


def test_session_deaths_settle_and_refund_a_missed_match(lg, staff, stats):
    day = PlayerMatchResult.objects.filter(player=stats).first().match.match_day
    fixture = Fixture.objects.create(
        season=lg["season"], date=day.date, session="8PM", scheduled_at=timezone.now(),
        match_day=day,
    )  # fmt: skip
    m = _player_market(lg, staff, C.SESSION_DEATHS, stats, 3, fixture)
    from apps.results.standings import rebuild_season

    rebuild_season(lg["season"])
    result = suggest(m)
    assert result["kind"] == "SETTLE" and result["note"] == "3 deaths in the session."
    assert m.outcomes.get(pk=result["winners"][0]).code == "yes"
    PlayerMatchResult.objects.filter(player=stats, match__match_day=day).last().delete()
    rebuild_season(lg["season"])
    result = suggest(m)
    assert result["kind"] == "VOID" and "missed a match" in result["note"]
