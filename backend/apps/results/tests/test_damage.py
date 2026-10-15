"""Damage dealt and taken, from the hits in the replay .bin."""

import datetime as dt

import pytest
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APIClient

from apps.ingest.parsers import replay_bin
from apps.league.models import Match, MatchDay, Player, ScoringRule, Season, Stage, Team
from apps.league.serializers import PlayerResultSerializer
from apps.results.damage import build_damage, coverage, totals
from apps.results.models import MatchDamage, MatchEvent, PlayerMatchResult
from apps.rotations.tests.replay_bin_factory import _zz, build

# Entity ids: the top byte is the team slot.
A1, A2, B1 = (1 << 24) | 1, (1 << 24) | 2, (2 << 24) | 3


def hit(t, attacker, victim, damage, weapon, part=2):
    return (t, 106, [attacker, victim, damage, 0, _zz(weapon), 0, 0, part])


HITS = [
    hit(10.0, A1, B1, 90, 635),  # AWM
    hit(11.0, A2, B1, 60, 21),
    hit(11.0, A2, B1, 60, 21),  # same moment, a second pellet: both count
    hit(12.0, B1, A1, 40, 21),
    hit(13.0, A1, A2, 15, 50),  # a grenade on a team-mate: not counted
    hit(14.0, B1, B1, 2, -1),  # the zone
    hit(15.0, A1, B1, 70, 635),
]


def replay():
    return build({A1: [(1.0, 0, 0, 0)], B1: [(1.0, 5, 0, 5)]}, extra=HITS)


def test_parser_reads_every_hit():
    hits = replay_bin.parse_hits(replay())
    assert len(hits) == len(HITS)
    t, attacker, victim, damage, weapon, part = hits[0]
    assert (t, attacker, victim, damage, weapon, part) == (10.0, A1, B1, 90, 635, 2)
    assert hits[5][4] == -1  # zone
    assert replay_bin.parse_hits(b"\x00garbage") == []


def test_totals_count_enemies_only_and_zone_apart():
    dealt, taken, zone = totals(replay_bin.parse_hits(replay()))
    assert dealt[A1] == 160 and dealt[A2] == 120 and dealt[B1] == 40
    assert taken[B1] == 280 and taken[A1] == 40 and taken[A2] == 0
    assert zone[B1] == 2


def test_coverage_is_the_share_of_deaths_with_damage_before_them():
    hits = replay_bin.parse_hits(replay())
    assert coverage(hits, [(15.5, B1)]) == 1
    assert coverage(hits, [(15.5, B1), (15.5, A2)]) == 0.5  # nothing hit A2
    assert coverage(hits, [(80.0, B1)]) == 0  # long after the hits
    assert coverage(hits, []) is None


@pytest.fixture
def match(db):
    rule, _ = ScoringRule.objects.get_or_create(name="Test rule", defaults={"placement_points": {}})
    stage = Stage.objects.create(season=Season.objects.create(name="S1", scoring_rule=rule))
    day = MatchDay.objects.create(stage=stage, number=1, date=dt.date(2026, 10, 13))
    m = Match.objects.create(match_day=day, number=1, status=Match.Status.PUBLISHED)
    alpha, bravo = Team.objects.create(name="Alpha"), Team.objects.create(name="Bravo")
    for entity, team, name in [(A1, alpha, "ACE"), (A2, alpha, "TWO"), (B1, bravo, "FOE")]:
        p = Player.objects.create(
            game_uid=entity, current_name_raw=name, display_name=name, search_name=name.lower()
        )
        PlayerMatchResult.objects.create(
            match=m, player=p, team=team, raw_name=name, display_name=name, entity_id=entity
        )
    MatchEvent.objects.create(
        match=m, kind=MatchEvent.Kind.KILL, source="DEBUGGER", game_time_s=15.2,
        actor_entity=A1, target_entity=B1,
    )  # fmt: skip
    return m


def damage_of(match):
    return {
        r.entity_id: (r.damage_dealt, r.damage_taken, r.zone_damage)
        for r in PlayerMatchResult.objects.filter(match=match)
    }


def test_build_damage_fills_players_and_replay_hits(match):
    assert build_damage(match, replay()) is None
    assert damage_of(match) == {A1: (160, 40, 0), A2: (120, 0, 0), B1: (40, 280, 2)}
    hits = MatchDamage.objects.get(match=match).hits
    assert hits[0] == [10.0, A1, B1, 90] and len(hits) == 5  # no team-mate or zone hits

    with override_settings(PUBLIC_SITE=True):
        data = APIClient().get(f"/api/v1/matches/{match.pk}/replay").json()
    assert data["hits"] == hits
    ace = PlayerResultSerializer(PlayerMatchResult.objects.get(match=match, entity_id=A1)).data
    assert (ace["damage_dealt"], ace["damage_taken"], ace["zone_damage"]) == (160, 40, 0)


def test_a_replay_missing_hits_gives_no_damage_rather_than_wrong_damage(match):
    build_damage(match, replay())
    MatchEvent.objects.create(
        match=match, kind=MatchEvent.Kind.KILL, source="DEBUGGER", game_time_s=90.0,
        actor_entity=B1, target_entity=A2,
    )  # fmt: skip
    problem = build_damage(match, replay())
    assert problem and "50% of deaths" in problem
    assert set(damage_of(match).values()) == {(None, None, None)}
    assert not MatchDamage.objects.filter(match=match).exists()


def test_fill_damage_skips_matches_without_a_replay(match):
    Match.objects.filter(pk=match.pk).update(game_match_id=123)
    call_command("fill_damage")
    assert set(damage_of(match).values()) == {(None, None, None)}
