"""Auto-drafted rotations and the plotting tool API."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Membership, User
from apps.league.models import Match, MatchDay, ScoringRule, Season, Stage, Team
from apps.maps.models import Map, MapArea
from apps.results.models import MatchEvent, TeamMatchResult, ZonePhase
from apps.rotations.auto import draft_rotations
from apps.rotations.models import RotationPoint, TeamRotation

pytestmark = pytest.mark.django_db
K = MatchEvent.Kind


@pytest.fixture
def match() -> Match:
    """Alpha wins; Bravo is eliminated at 450s. Zones shrink at 200, 400 and 600s."""
    season = Season.objects.create(name="S1", scoring_rule=ScoringRule.objects.first())
    day = MatchDay.objects.create(stage=Stage.objects.create(season=season, name="L"), number=1)
    match = Match.objects.create(
        match_day=day,
        number=1,
        map=Map.objects.get(slug="purgatory"),
        status=Match.Status.PUBLISHED,
    )
    alpha, bravo = Team.objects.create(name="Alpha"), Team.objects.create(name="Bravo")
    for team, placement, eliminated in [(alpha, 1, None), (bravo, 2, 450.0)]:
        TeamMatchResult.objects.create(
            match=match,
            team=team,
            in_game_name=team.name,
            placement=placement,
            kills=0,
            placement_points=0,
            kill_points=0,
            total_points=0,
            eliminated_at_s=eliminated,
        )
    for stage, t in enumerate([200.0, 400.0, 600.0]):
        ZonePhase.objects.create(
            match=match,
            stage_index=stage,
            state="SHRINK",
            game_time_s=t,
            outer_x=0,
            outer_z=0,
            inner_x=0,
            inner_z=0,
            inner_radius=300 / (stage + 1),
        )

    def ev(kind, t, team, x, z, target=None, tx=None, tz=None):
        MatchEvent.objects.create(
            match=match,
            kind=kind,
            source="REPLAY_INFO",
            game_time_s=t,
            actor_team=team,
            target_team=target,
            x=x,
            z=z,
            tx=tx,
            tz=tz,
        )

    ev(K.KILL, 100, alpha, 10, 10, bravo, 21, 21)  # early fight: both drops
    ev(K.DEATH, 100, bravo, 20, 20)  # the same death from DeadEvents wins over the kill's copy
    ev(K.KILL, 120, alpha, 12, 14)
    ev(K.RESPAWN, 130, bravo, 500, 500)  # respawns don't count for the drop
    ev(K.KILL, 250, alpha, 100, 100)
    ev(K.KILL, 260, alpha, 110, 90)
    ev(K.KILL, 270, alpha, 400, 400)  # an outlier: the median ignores it
    ev(K.TELEPORT, 300, bravo, -50, -50)
    ev(K.DEATH, 449, bravo, -60, -40)  # Bravo's last player dies
    ev(K.KILL, 460, bravo, -70, -70)  # after elimination + slack: ignored
    ev(K.KILL, 700, alpha, 5, 6)
    ev(K.KNOCK, 710, alpha, None, None)
    return match


def points_of(match: Match, name: str) -> list[tuple]:
    rotation = TeamRotation.objects.get(match=match, team__name=name)
    return [(p.checkpoint, p.x, p.z, p.source) for p in rotation.points.all()]


def test_auto_draft(match):
    assert draft_rotations(match) == 2
    assert points_of(match, "Alpha") == [
        ("DROP", 11.0, 12.0, "AUTO"),
        ("ZONE_1", 110.0, 100.0, "AUTO"),
        ("ZONE_3", 5.0, 6.0, "AUTO"),
        ("FINAL", 5.0, 6.0, "AUTO"),
    ]
    # Bravo: the drop is where its player died in the first fight.
    assert points_of(match, "Bravo") == [
        ("DROP", 20.0, 20.0, "AUTO"),
        ("ZONE_1", -50.0, -50.0, "AUTO"),
        ("ZONE_2", -60.0, -40.0, "AUTO"),
        ("ELIMINATED", -60.0, -40.0, "AUTO"),
    ]
    zone1 = TeamRotation.objects.get(team__name="Alpha").points.get(checkpoint="ZONE_1")
    assert zone1.evidence == {"kills": 3} and zone1.game_time_s == 260


def test_redraft_keeps_staff_edits_and_areas_are_filled(match):
    MapArea.objects.create(
        map=match.map, name="Brasilia", polygon=[[0, 0], [50, 0], [50, 50], [0, 50]]
    )
    draft_rotations(match)
    alpha = TeamRotation.objects.get(team__name="Alpha")
    assert alpha.points.get(checkpoint="DROP").area.name == "Brasilia"
    alpha.status = TeamRotation.Status.CONFIRMED
    alpha.save()
    alpha.points.filter(checkpoint="ZONE_1").update(x=1, z=1)

    ZonePhase.objects.filter(match=match).delete()
    draft_rotations(match)  # e.g. a re-upload without a debugger log
    assert ("ZONE_1", 1.0, 1.0, "AUTO") in points_of(match, "Alpha")  # kept
    assert [p[0] for p in points_of(match, "Bravo")] == ["ELIMINATED"]  # redrafted


def test_teams_that_left_the_results_lose_their_auto_draft(match):
    draft_rotations(match)
    TeamMatchResult.objects.filter(team__name="Bravo").delete()
    draft_rotations(match)
    assert list(TeamRotation.objects.values_list("team__name", flat=True)) == ["Alpha"]


# -- API --------------------------------------------------------------------------------------


@pytest.fixture
def staff() -> APIClient:
    client = APIClient()
    client.force_authenticate(User.objects.create_user(email="s@tdl.test", is_staff=True))
    return client


def team_client(team: Team) -> APIClient:
    user = User.objects.create_user(email=f"{team.slug}@tdl.test")
    Membership.objects.create(user=user, team=team, role=Membership.Role.PLAYER)
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_read_zones_and_rotations_needs_the_feature(match):
    draft_rotations(match)
    alpha_player = team_client(Team.objects.get(name="Alpha"))
    zones = alpha_player.get(f"/api/v1/matches/{match.pk}/zones").json()
    assert zones["map"]["slug"] == "purgatory" and len(zones["zones"]) == 3
    data = alpha_player.get(f"/api/v1/matches/{match.pk}/rotations").json()
    assert [r["team"]["name"] for r in data["rotations"]] == ["Alpha", "Bravo"]
    assert data["rotations"][0]["placement"] == 1
    assert data["rotations"][0]["points"][0]["checkpoint"] == "DROP"

    outsider = team_client(Team.objects.create(name="Guest", is_league_member=False))
    assert outsider.get(f"/api/v1/matches/{match.pk}/rotations").status_code == 403
    assert APIClient().get(f"/api/v1/matches/{match.pk}/zones").status_code == 401

    match.status = Match.Status.NEEDS_REVIEW
    match.save()
    assert alpha_player.get(f"/api/v1/matches/{match.pk}/rotations").status_code == 404


def test_plot_confirm_and_reset(match, staff):
    MapArea.objects.create(
        map=match.map, name="Mars", polygon=[[-90, -90], [-30, -90], [-30, -30], [-90, -30]]
    )
    url = f"/api/v1/matches/{match.pk}/rotations/bravo"
    auto = staff.get(url).json()  # the first open drafts it
    assert auto["status"] == "AUTO" and auto["points"][0]["checkpoint"] == "DROP"

    kept = auto["points"][0]  # sent back unchanged: keeps AUTO and its evidence
    resp = staff.put(
        url,
        {
            "points": [
                {"checkpoint": "DROP", "x": kept["x"], "z": kept["z"]},
                {"checkpoint": "ZONE_1", "x": -60, "z": -60, "game_time_s": 300, "note": "cliff"},
                {"checkpoint": "EXTRA", "x": -40, "z": -40},
                {"checkpoint": "EXTRA", "x": -45, "z": -45},
                {"checkpoint": "ELIMINATED", "x": -61, "z": -41},
            ]
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    saved = resp.json()
    assert saved["status"] == "DRAFT" and saved["plotted_by"] == "s@tdl.test"
    assert [(p["checkpoint"], p["source"]) for p in saved["points"]][:2] == [
        ("DROP", "AUTO"),
        ("ZONE_1", "MANUAL"),
    ]
    assert saved["points"][0]["evidence"] == {"deaths": 1}
    assert saved["points"][1]["area"] == "Mars" and saved["points"][1]["note"] == "cliff"

    confirmed = staff.post(f"{url}/confirm").json()
    assert confirmed["status"] == "CONFIRMED" and confirmed["confirmed_at"]
    staff.put(url, {"points": [{"checkpoint": "DROP", "x": 1, "z": 1}]}, format="json")
    assert TeamRotation.objects.get(team__slug="bravo").status == "DRAFT"  # edits reopen it

    reset = staff.post(f"{url}/reset").json()
    assert reset["status"] == "AUTO" and len(reset["points"]) == 4
    assert staff.get(f"{url}/confirm").status_code == 405


def test_plot_validation(match, staff):
    url = f"/api/v1/matches/{match.pk}/rotations/alpha"
    bad = [
        {
            "points": [
                {"checkpoint": "DROP", "x": 1, "z": 1},
                {"checkpoint": "DROP", "x": 2, "z": 2},
            ]
        },
        {
            "points": [
                {"checkpoint": "FINAL", "x": 1, "z": 1},
                {"checkpoint": "ELIMINATED", "x": 1, "z": 1},
            ]
        },
        {"points": [{"checkpoint": "ZONE_9", "x": 1, "z": 1}]},
        {"points": [{"checkpoint": "DROP", "x": 99999, "z": 1}]},
        {"points": [{"checkpoint": "DROP", "x": 1, "z": 1, "game_time_s": -5}]},
        {"points": [{"checkpoint": "EXTRA", "x": 1, "z": 1}] * 61},
        {"nope": []},
    ]
    for body in bad:
        assert staff.put(url, body, format="json").status_code == 400, body

    staff.put(url, {"points": []}, format="json")
    assert staff.post(f"{url}/confirm").status_code == 400  # nothing to confirm
    Team.objects.create(name="Charlie")
    assert staff.get(f"/api/v1/matches/{match.pk}/rotations/charlie").status_code == 400
    assert staff.get(f"/api/v1/matches/{match.pk}/rotations/nobody").status_code == 404

    player = team_client(Team.objects.get(name="Alpha"))
    assert player.put(url, {"points": []}, format="json").status_code == 403


def test_redraft_endpoint_and_area_relabel(match, staff):
    resp = staff.post(f"/api/v1/matches/{match.pk}/redraft-rotations")
    assert resp.json() == {"drafted": 2}
    assert not RotationPoint.objects.filter(area__isnull=False).exists()

    boss = APIClient()
    boss.force_authenticate(
        User.objects.create_user(email="boss@tdl.test", is_staff=True, is_superuser=True)
    )
    area = boss.post(
        "/api/v1/admin/maps/purgatory/areas",
        {"name": "Mars", "polygon": [[-90, -90], [-30, -90], [-30, -30], [-90, -30]]},
        format="json",
    ).json()
    labelled = RotationPoint.objects.filter(area__name="Mars")
    assert sorted(labelled.values_list("checkpoint", flat=True)) == [
        "ELIMINATED",
        "ZONE_1",
        "ZONE_2",
    ]
    boss.delete(f"/api/v1/admin/maps/purgatory/areas/{area['id']}")
    assert not RotationPoint.objects.filter(area__isnull=False).exists()


def test_admin_match_list_shows_plotting_progress(match, staff):
    draft_rotations(match)
    staff.post(f"/api/v1/matches/{match.pk}/rotations/alpha/confirm")
    row = staff.get("/api/v1/admin/matches").json()["results"][0]
    assert row["rotations"] == {"AUTO": 1, "DRAFT": 0, "CONFIRMED": 1}
    assert row["label"] == str(match)
