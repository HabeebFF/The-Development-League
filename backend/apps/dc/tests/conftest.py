"""Shared fixtures for the DC tests: a small league with one linked player."""

import pytest

from apps.accounts.models import User
from apps.dc.models import DcSettings
from apps.league.models import Match, MatchDay, Player, ScoringRule, Season, Stage, Team
from apps.predictions.services import lagos_today
from apps.results.models import PlayerMatchResult, TeamMatchResult

PASSWORD = "a-Long-password-42"


@pytest.fixture(autouse=True)
def _on(settings):
    settings.DC_MATCH_REWARDS = True


def make_user(email: str) -> User:
    return User.objects.create_user(email=email, password=PASSWORD, display_name=email[:5])


@pytest.fixture
def league():
    rule, _ = ScoringRule.objects.get_or_create(name="Test rule", defaults={"placement_points": {}})
    season = Season.objects.create(name="S1", slug="s1", scoring_rule=rule)
    stage = Stage.objects.create(season=season, name="Scrims")
    alpha, bravo = Team.objects.create(name="Alpha"), Team.objects.create(name="Bravo")
    players = {
        "a1": Player.objects.create(
            game_uid=101, current_name_raw="A1", display_name="A1", search_name="a1",
            current_team=alpha,
        ),
        "a2": Player.objects.create(
            game_uid=102, current_name_raw="A2", display_name="A2", search_name="a2",
            current_team=alpha,
        ),
        "b1": Player.objects.create(
            game_uid=201, current_name_raw="B1", display_name="B1", search_name="b1",
            current_team=bravo,
        ),
    }  # fmt: skip
    user = make_user("a1@tdl.test")
    players["a1"].user = user
    players["a1"].save()
    DcSettings.get()  # start day = today
    return {"season": season, "stage": stage, "alpha": alpha, "bravo": bravo, "p": players,
            "user": user}  # fmt: skip


def upload(league, number=1, kills=None, winner="alpha", date=None, status=None):
    """A published match: Alpha (a1, a2) and Bravo (b1); ``kills`` per player key."""
    kills = kills or {"a1": 3, "a2": 1, "b1": 2}
    day, _ = MatchDay.objects.get_or_create(
        stage=league["stage"], number=1, defaults={"title": "TDL DAY 1 8PM",
                                                   "date": date or lagos_today()},
    )  # fmt: skip
    if date:
        day = MatchDay.objects.create(stage=league["stage"], number=number + 10, date=date)
    match = Match.objects.create(
        match_day=day, number=number, status=status or Match.Status.PUBLISHED
    )
    for key, team in (("alpha", league["alpha"]), ("bravo", league["bravo"])):
        TeamMatchResult.objects.create(
            match=match, team=team, in_game_name=team.name, placement=1 if key == winner else 2,
            kills=0, placement_points=0, kill_points=0, total_points=0,
        )  # fmt: skip
    for key, n in kills.items():
        p = league["p"][key]
        PlayerMatchResult.objects.create(
            match=match, player=p, team=p.current_team, raw_name=p.display_name,
            display_name=p.display_name, kills=n,
        )  # fmt: skip
    return match
