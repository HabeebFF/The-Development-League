"""Build small ReplayInfo .bin files in the real layout, for tests."""

import struct


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        c, n = n & 0x7F, n >> 7
        out.append(c | 0x80 if n else c)
        if not n:
            return bytes(out)


def _zz(n: int) -> int:
    return (n << 1) ^ (n >> 63)


def _message(t: float, kind: int, payload: bytes) -> bytes:
    return b"\x00" + struct.pack("<fBHH", t, 0, kind, len(payload)) + payload


def build(
    samples: dict[int, list[tuple[float, float, float, float]]], header_t: float = 0.0
) -> bytes:
    """``samples``: entity id -> [(t, x, y, z)]. One position message per time."""
    out = bytearray(_message(header_t, 100, b"\x01\x02\x03"))
    state = [_zz(len(samples))]
    for entity in samples:
        state += [entity] + [0] * 12
    out += _message(header_t, 2055, b"".join(_varint(v) for v in state))
    by_time: dict[float, list[tuple[int, float, float, float]]] = {}
    for entity, rows in samples.items():
        for t, x, y, z in rows:
            by_time.setdefault(t, []).append((entity & 0xFFFFFF, x, y, z))
    for frame, t in enumerate(sorted(by_time)):
        rows = by_time[t]
        tokens = [0, _zz(len(rows))]
        for low, x, y, z in rows:
            tokens += [low] + [_zz(round(v * 1000)) for v in (x, y, z)] + [0] * 15
        tokens += [0, frame]
        out += _message(t, 2054, b"".join(_varint(v) for v in tokens))
    return bytes(out)
