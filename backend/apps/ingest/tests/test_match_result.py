from apps.ingest.parsers import match_result

NAME = "MatchResult_2103980121133858816_2026-09-27-00-05-01.log"

SPEC_LINES = (
    "TeamName: NOOBZ ESPORTS        Rank: 1    KillScore: 17   RankScore: 12   TotalScore: 29\n"
    "NAME: NBㅤVALSIᴰˢ           ID: 2063288734           KILL: 9\n"
)


def test_spec_sample_lines():
    result = match_result.parse(NAME, SPEC_LINES)
    team = result.data.teams[0]
    assert (team.name, team.rank, team.kill_score, team.rank_score, team.total_score) == (
        "NOOBZ ESPORTS",
        1,
        17,
        12,
        29,
    )
    player = team.players[0]
    assert player.name_raw == "NBㅤVALSIᴰˢ"
    assert player.display_name == "NB VALSIᴰˢ"
    assert player.uid == 2063288734
    assert player.kills == 9
    # Only one of four players given, so the kill check fires.
    assert [w.code for w in result.warnings] == ["kill_mismatch"]


def test_real_file(match_result_bytes):
    result = match_result.parse(NAME, match_result_bytes)
    data = result.data
    assert result.warning_count == 0, result.warnings
    assert data.match_id == 2103980121133858816
    assert len(data.teams) == 13
    assert len(data.players) == 52
    assert [t.rank for t in data.teams] == list(range(1, 14))
    assert sum(p.kills for p in data.players) == 89

    by_uid = {p.uid: p for p in data.players}
    assert by_uid[11559421022].name_raw == "RBL\u205fAMK"  # 11-digit UID, odd space
    assert by_uid[11559421022].display_name == "RBL AMK"
    assert by_uid[3973124752].display_name == "S&U LIGHT"  # U+1160 filler
    assert data.team_of(90188171).name == "OUTPOST33 ESP"


def test_default_rank_points_seen_in_logs(match_result_bytes):
    data = match_result.parse(NAME, match_result_bytes).data
    table = {1: 12, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
    for team in data.teams:
        assert team.rank_score == table.get(team.rank, 0)
        assert team.total_score == team.kill_score + team.rank_score


def test_teams_with_fewer_players_and_unknown_lines():
    text = (
        "TeamName: A        Rank: 2    KillScore: 1   RankScore: 9   TotalScore: 10\n"
        "NAME: one           ID: 1           KILL: 1\n"
        "garbage here\n"
        "\n"
        "TeamName: B        Rank: 1    KillScore: 0   RankScore: 12   TotalScore: 12\n"
        "NAME: two           ID: 2           KILL: 0\n"
    )
    result = match_result.parse(NAME, text)
    assert [t.name for t in result.data.teams] == ["A", "B"]
    assert [w.code for w in result.warnings] == ["unparsed_line"]
    assert result.warnings[0].line_no == 3


def test_validation_warnings():
    text = (
        "NAME: orphan           ID: 9           KILL: 0\n"
        "TeamName: A        Rank: 1    KillScore: 5   RankScore: 12   TotalScore: 99\n"
        "NAME: one           ID: 1           KILL: 1\n"
        "NAME: dup           ID: 1           KILL: 0\n"
        "TeamName: B        Rank: 1    KillScore: 0   RankScore: 12   TotalScore: 12\n"
    )
    codes = {w.code for w in match_result.parse(NAME, text).warnings}
    assert codes == {
        "player_without_team",
        "duplicate_uid",
        "kill_mismatch",
        "total_mismatch",
        "empty_team",
        "duplicate_rank",
    }


def test_empty_file_never_raises():
    result = match_result.parse(NAME, b"\xef\xbb\xbf")
    assert result.data.teams == []
    assert result.warnings[0].code == "no_teams"
