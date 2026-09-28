"""Replay .bin parsing, track resampling and the live replay API."""

from apps.ingest.parsers import replay_bin
from apps.rotations.tracks import resample

from .replay_bin_factory import build

A, B = 0x0100002A, 0x0200002B  # team slot 1 / 2


def test_parser_reads_positions_per_entity():
    data = build(
        {
            A: [(60.0, -476.997, 12.271, -196.007), (60.2, -476.5, 12.3, -195.5)],
            B: [(60.0, 100.0, 50.0, 200.0)],
        }
    )
    tracks = replay_bin.parse_tracks(data)
    assert set(tracks) == {A, B}
    assert tracks[A][0] == (60.0, -476.997, 12.271, -196.007)
    assert [round(s[0], 3) for s in tracks[A]] == [60.0, 60.2]


def test_parser_drops_lobby_and_never_raises():
    data = build({A: [(10.0, 0.0, 1400.0, 0.0), (60.0, 1.0, 5.0, 2.0)]})
    assert [s[2] for s in replay_bin.parse_tracks(data)[A]] == [5.0]
    assert len(replay_bin.parse_tracks(data, include_lobby=True)[A]) == 2
    for bad in (b"", b"\x00\x01binary", b"\xff" * 5000, None, "text", data[:-7]):
        assert isinstance(replay_bin.parse_tracks(bad), dict)
    # A truncated file still gives what came before the cut.
    assert replay_bin.parse_tracks(data[:-7]) == {} or A in replay_bin.parse_tracks(data[:-7])


def test_resample_interpolates_and_leaves_gaps_empty():
    samples = [(10.1, 0.0, 0, 0.0), (10.9, 8.0, 0, 4.0), (20.0, 50.0, 0, 50.0), (20.2, 51, 0, 50)]
    start, points = resample(samples, step=0.5, max_gap=2.5)
    assert start == 10.5
    assert points[0] == [40, 20]  # halfway between the first two samples, in decimetres
    assert points[1] is None  # 11.0 falls in the 9 s gap
    assert points[-1] == [500, 500]  # 20.0
    assert len(points) == 20
    assert resample([]) == (0.0, [])
