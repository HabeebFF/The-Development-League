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
    samples: dict[int, list[tuple[float, float, float, float]]],
    header_t: float = 0.0,
    extra: list[tuple[float, int, list[int]]] = (),
) -> bytes:
    """``samples``: entity id -> [(t, x, y, z)]. One position message per time.

    ``extra`` adds other messages as (t, type, varints), sorted in by time.
    """
    out = bytearray(_message(header_t, 100, b"\x01\x02\x03"))
    state = [_zz(len(samples))]
    for entity in samples:
        state += [entity] + [0] * 12
    out += _message(header_t, 2055, b"".join(_varint(v) for v in state))
    by_time: dict[float, list[tuple[int, float, float, float]]] = {}
    for entity, rows in samples.items():
        for t, x, y, z in rows:
            by_time.setdefault(t, []).append((entity & 0xFFFFFF, x, y, z))
    messages = []
    for frame, t in enumerate(sorted(by_time)):
        rows = by_time[t]
        tokens = [0, _zz(len(rows))]
        for low, x, y, z in rows:
            tokens += [low] + [_zz(round(v * 1000)) for v in (x, y, z)] + [0] * 15
        tokens += [0, frame]
        messages.append((t, 2054, tokens))
    messages += list(extra)
    for t, kind, tokens in sorted(messages, key=lambda m: m[0]):
        out += _message(t, kind, b"".join(_varint(v) for v in tokens))
    return bytes(out)


def mm(v: float) -> int:
    """A coordinate in metres as the zigzag millimetre varint value."""
    return _zz(round(v * 1000))


def uav(t: float, object_id: int, owner: int, kind: int, x: float, y: float, z: float):
    """One type-2005 flying-object sample."""
    radius = 200 if kind == 1006 else 500
    return (t, 2005, [object_id, 0, mm(x), mm(y), mm(z), 1, owner, kind, 0, 0, radius, radius, 7])


def bolt(t: float, caster: int, x: float, z: float, strikes: int = 30):
    """One type-157 Bolt Maker lightning zone, a strike every 2 s."""
    body = []
    for i in range(strikes):
        body += [mm(x + i % 3), mm(z - i % 2), 4400, 5000 + i * 2000]
    return (t, 157, [mm(x), mm(z), 20000, 0, 60, *body, caster >> 24, 3, caster])
