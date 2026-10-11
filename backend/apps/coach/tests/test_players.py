"""Player cards: per-match counts for each player, added up and compared with the league."""

from apps.coach.engine import Hit
from apps.coach.moments import Player
from apps.coach.players import GAP, cards, match_rows
from apps.coach.tests.test_moments import NAMES, game, line, published, squad, still  # noqa: F401
from apps.rotations.paths import Track


def rows_by_name(rows):
    return {r["name"]: r for r in rows}


def test_counts_kills_weapons_and_utility():
    players = squad(1, (0, 0), (5, 0), (0, 5), (5, 5))
    hits = [
        Hit(100, "KNOCK", 1, 2, 21, actor=11),
        Hit(104, "KILL", 1, 2, 21, actor=11, weapon=635),
        Hit(140, "KILL", 1, 2, 22, actor=11, weapon=0),  # no weapon logged: not counted
        Hit(150, "KILL", 1, 1, 13, actor=11),  # own team: never a kill
    ]
    rows = rows_by_name(
        match_rows(game(hits), 1, players, [(11, "PLAYER_UAV"), (12, "DINOCULARS")])
    )
    p11 = rows["P11"]
    assert (p11["kills"], p11["knocks"], p11["weapons"]) == (2, 1, {"635": 1})
    assert p11["utility"] == {"uav": 1} and rows["P12"]["utility"] == {"scan": 1}
    assert len(rows) == 4


def test_alone_downs_and_first_down():
    players = squad(1, (200, 0), (0, 0), (5, 0), (0, 5))
    hits = [Hit(150, "KNOCK", 2, 1, 11, actor=21), Hit(300, "KNOCK", 2, 1, 12, actor=21)]
    rows = rows_by_name(match_rows(game(hits), 1, players))
    assert (rows["P11"]["alone_downs"], rows["P11"]["known_downs"]) == (1, 1)
    assert rows["P11"]["first_down"] and not rows["P12"]["first_down"]
    assert (rows["P12"]["alone_downs"], rows["P12"]["known_downs"]) == (0, 1)
    assert rows["P11"]["clips"]["alone"] == [150]


def test_trades_count_only_the_players_own_knock_back_on_the_attackers():
    players = squad(1, (0, 0), (5, 0), (0, 5), (500, 0))
    hits = [
        Hit(150, "KNOCK", 2, 1, 11, actor=21),
        Hit(155, "KNOCK", 1, 2, 21, actor=12),  # P12 trades
        Hit(170, "KNOCK", 1, 3, 31, actor=13),  # P13 hits someone else: not a trade
    ]
    rows = rows_by_name(match_rows(game(hits), 1, players))
    assert (rows["P12"]["trades"], rows["P12"]["trade_chances"]) == (1, 1)
    assert (rows["P13"]["trades"], rows["P13"]["trade_chances"]) == (0, 1)
    assert rows["P13"]["clips"]["missed_trade"] == [150]
    assert rows["P14"]["trade_chances"] == 0  # 500 m away: no chance


def test_spacing_from_landing_until_the_last_sample():
    far = Player(1, "Far", line((0, 300, 0), (400, 300, 0)))
    near = {11: Player(1, "A", still(0, 0)), 12: Player(1, "B", still(10, 0))}
    rows = rows_by_name(match_rows(game(), 1, {**near, 13: far}))
    assert rows["Far"]["spacing_m"] == 290 and rows["Far"]["far"] == rows["Far"]["samples"]
    assert rows["Far"]["alive_s"] == 400
    assert rows["A"]["spacing_m"] == 10 and rows["A"]["far"] == 0
    # No track: nothing to sample.
    no_track = match_rows(game(), 1, {11: Player(1, "Ghost", None), 12: near[12]})
    assert rows_by_name(no_track)["Ghost"]["spacing_m"] is None


def row(match, name="Ace", player=7, **counts):
    base = {
        "entity": 1, "player": player, "name": name, "kills": 0, "knocks": 0, "weapons": {},
        "downs": 0, "known_downs": 0, "alone_downs": 0, "trade_chances": 0, "trades": 0,
        "first_down": False, "spacing_m": 20, "far": 0, "samples": 100, "alive_s": 900,
        "utility": {}, "clips": {"alone": [], "missed_trade": [], "first_down": []}, "match": match,
    }  # fmt: skip
    return {**base, **counts}


def test_card_picks_the_biggest_gap_from_the_league_and_links_clips():
    team = [
        row(m, known_downs=2, alone_downs=2, downs=2, kills=3, weapons={"635": 2},
            clips={"alone": [100.0 + m], "missed_trade": [], "first_down": []})
        for m in (1, 2, 3)
    ]  # fmt: skip
    others = [row(m, name="Other", player=8, known_downs=4, alone_downs=0) for m in (1, 2, 3)]
    out = cards(team, team + others, {1: "Day 1 M1", 2: "Day 1 M2", 3: "Day 1 M3"}, {635: "AWM"})
    (card,) = out["players"]
    assert out["league"]["alone"] == 0.333  # 6 of 18 league downs
    assert card["rates"]["alone"] == 1.0 and card["kills_per_match"] == 3.0
    assert card["weapons"] == [{"name": "AWM", "kills": 6}]
    task = card["task"]
    assert task["title"] == "Stay close to your team"
    assert "6 of 6 downs" in task["why"] and "League average: 33%" in task["why"]
    assert [c["label"] for c in task["clips"]] == ["Day 1 M3", "Day 1 M2", "Day 1 M1"]
    assert task["clips"][0]["watch_s"] == 103 - 8


def test_no_task_without_enough_behind_it_and_strengths_when_ahead():
    few = [row(1, known_downs=2, alone_downs=2)]  # only 2 downs
    assert cards(few, few * 5, {}, {})["players"][0]["task"] is None

    good = [row(m, trade_chances=3, trades=3) for m in (1, 2)]
    weak = [row(m, name="B", player=9, trade_chances=10, trades=1) for m in (1, 2)]
    out = cards(good, good + weak, {}, {})
    assert out["league"]["trade"] < 1 - GAP
    assert out["players"][0]["strengths"][0].startswith("Trades fast: knocked back 6 of 6")


# -- API ---------------------------------------------------------------------------------------


def test_players_endpoint_builds_rows_and_is_private(published):  # noqa: F811
    from apps.coach.models import MatchReview
    from apps.coach.tests.test_moments import _member

    match, alpha, bravo = published
    a = _member(alpha, "a@tdl.test")
    resp = a.get("/api/v1/coach/teams/alpha/players?period=all")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["matches"] == 1 and body["pending"] == 0 and body["period"] == "all"
    assert {p["downs"] for p in body["players"]} == {0, 1}
    assert len(MatchReview.objects.get(team=alpha).players) == 2
    assert _member(bravo, "b@tdl.test").get("/api/v1/coach/teams/alpha/players").status_code == 403


def test_tracks_without_points_are_skipped():
    empty = Player(1, "Empty", Track(0, 0.5, [None, None]))
    rows = match_rows(game(), 1, {11: empty})
    assert rows[0]["spacing_m"] is None and rows[0]["alive_s"] is None
