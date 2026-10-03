from apps.coach.engine import (
    MIN_MATCHES,
    Area,
    Game,
    Hit,
    TeamGame,
    Zone,
    fights,
    measure,
    profile,
    zone_entries,
)
from apps.rotations.paths import TeamPath

SQUARE = [[-50, -50], [50, -50], [50, 50], [-50, 50]]


def walk(*points: tuple[float, float, float]) -> TeamPath:
    """A path through (t, x, z) points, one point a second in between."""
    seg = []
    for (t0, x0, z0), (t1, x1, z1) in zip(points, points[1:], strict=False):
        steps = int(t1 - t0)
        for i in range(steps):
            k = i / steps
            seg.append((t0 + i, x0 + (x1 - x0) * k, z0 + (z1 - z0) * k))
    seg.append(points[-1])
    return TeamPath([seg], points[0][0])


# Zone 1 at (0, 0) r=300 from 100 s, closes 300 s; Zone 2 at (0, 0) r=100 from 300 s, closes 500 s.
ZONES = [Zone(1, 0, 0, 300, 100, 300), Zone(2, 0, 0, 100, 300, 500)]


def game(match=1, teams=None, hits=(), map_="kalahari") -> Game:
    return Game(
        match, f"M{match}", map_, ZONES, list(hits), teams or {}, [Area("Refinery", SQUARE)]
    )


def test_zone_entry_early_late_and_where_they_stood():
    early = TeamGame(1, 1, None, walk((60, 400, 0), (150, 0, 0), (600, 0, 0)))
    late = TeamGame(2, 2, None, walk((60, 900, 0), (520, 50, 0), (600, 50, 0)))
    g = game(teams={1: early, 2: late})

    e = zone_entries(g, early)
    assert [x.zone for x in e] == [1, 2]
    assert e[0].lead_s == 200  # already inside when Zone 1 was shown at 100 s
    assert e[1].edge == 0.0

    lt = zone_entries(g, late)
    assert lt[0].lead_s is None  # not inside Zone 1 even a minute after it closed
    assert lt[0].edge > 1  # outside when it closed


def test_a_team_dead_before_a_zone_closes_is_not_judged_on_it():
    gone = TeamGame(1, 9, 250.0, walk((60, 0, 0), (250, 0, 0)))
    assert zone_entries(game(teams={1: gone}), gone) == []


def test_fights_group_hits_and_pick_a_winner():
    hits = [
        Hit(100, "KNOCK", 1, 2, 21, 0, 0),
        Hit(105, "KILL", 1, 2, 21, 0, 0),  # the same victim counts once
        Hit(110, "KNOCK", 2, 1, 11),
        Hit(120, "KNOCK", 1, 2, 22),
        Hit(400, "KNOCK", 2, 1, 12),  # a separate, later fight, lost
        Hit(130, "KILL", 3, 1, 13),  # a different opponent
    ]
    g = game(teams={1: TeamGame(1, 1, None, None)}, hits=hits)
    fs = fights(g, 1)
    vs2 = [f for f in fs if f.opponent == 2]
    assert [(f.result, f.started, f.downs_for, f.downs_against) for f in vs2] == [
        ("won", True, 2, 1),
        ("lost", False, 0, 1),
    ]
    assert vs2[0].place == "Refinery"
    assert vs2[0].zone == 1 and vs2[1].zone == 2


def test_drop_area_and_contested_drop():
    a = TeamGame(1, 3, None, walk((60, 0, 0), (100, 0, 0)))
    b = TeamGame(2, 5, None, walk((60, 120, 0), (100, 120, 0)))
    c = TeamGame(3, 7, None, walk((60, 900, 900), (100, 900, 900)))
    m = measure(game(teams={1: a, 2: b, 3: c}), 1)
    assert m.drop.name == "Refinery"
    assert m.contested_by == [2]


def test_facts_cite_their_matches_and_need_enough_of_them():
    def one(match, placement, lead_end, die_at=None):
        path = walk((60, 0, 0), (lead_end, 0, 0), (600, 0, 0))
        deaths = [(590.0, *die_at)] if die_at else []
        team = TeamGame(1, placement, None, path, deaths)
        rival = TeamGame(2, 2, None, walk((60, 100, 0), (600, 100, 0)))
        return measure(game(match, {1: team, 2: rival}, [Hit(200, "KNOCK", 1, 2, 21, 0, 0)]), 1)

    few = [one(i, 1, 120) for i in range(MIN_MATCHES - 1)]
    assert profile(few)["facts"] == []

    played = [one(1, 1, 120, (0, 0)), one(2, 4, 120, (10, 10)), one(3, 2, 120), one(4, 8, 120)]
    facts = {f["id"]: f for f in profile(played, {2: "Rivals"})["facts"]}

    assert facts["results.placement"]["text"] == "Average placement: 3.8 over 4 matches"
    assert facts["results.booyah"]["matches"] == [1]
    assert facts["fights.record"]["text"] == "Won 4, lost 0 of 4 fights"
    assert facts["fights.vs2"]["text"].startswith("Against Rivals: won 4")
    assert facts["deaths.top1"]["text"] == "2 player deaths at Refinery, in 2 of 4 matches"
    assert facts["deaths.top1"]["matches"] == [1, 2]
    assert facts["position.edge"]["value"] == 0.0
    # Every fact says which matches it rests on, and they're real ones.
    for f in facts.values():
        assert f["matches"] and set(f["matches"]) <= {1, 2, 3, 4}
        assert f["n"] <= f["of"]
    # Per map: the drop.
    assert facts["kalahari:drops.usual"]["text"].startswith(
        "Usual drop on Kalahari: Refinery, in 4 of 4"
    )
