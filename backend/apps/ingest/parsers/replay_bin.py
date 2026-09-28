"""ReplayInfo_*.bin: the client replay, with every player's position ~5 times a second.

Extracts a movement track for every player entity:

    parse_tracks(data) -> {entity_id: [(t, x, y, z), ...]}   # time-sorted

t is game time in seconds (same clock as the companion .json's Time /
TriggerPoint fields), x/y/z are metres in the same world frame as the .json
Position fields (y is height).

Layout (reverse-engineered 2026-09-28, checked against the .json kill and death
positions: median error under 0.5 m):

- The file is a chain of messages [0x00][f32 time][u8 flag][u16 type][u16 len][payload]
  (little-endian). time is game seconds, the same clock as the .json.
- Type 2054 holds positions: 0, zigzag(N), then N records of 19 unsigned LEB128
  varints (player index = low 24 bits of the entity id, then x, y, z as zigzag
  millimetres, then 15 fields not decoded), then 0 and a frame counter.
- Type 2055 holds player state: zigzag(N), then N records of 13 varints; the first
  is the full entity id (team slot in the top byte), which maps index -> entity id.
- Players are not in the feed while on the plane or while dead; lobby samples sit at
  y ~ 1400 m and are dropped.

Standard library only. Never raises on bad or truncated data: it resyncs on the next
valid message and skips what it cannot decode.
"""

from __future__ import annotations

import struct

__all__ = ["parse_tracks", "parse_replay", "iter_messages", "MSG_POSITIONS", "MSG_ENTITY_STATE"]

MSG_POSITIONS = 2054  # 0x0806: batch of per-player position records
MSG_ENTITY_STATE = 2055  # 0x0807: batch of per-player state, carries full ids

_HDR = struct.Struct("<fBHH")  # time, flag, msg type, payload length
_REC_LEN = 19  # varints per position record
_STATE_REC_LEN = 13  # varints per 2055 record
_LOBBY_MIN_Y = 1000.0  # pre-match lobby island sits at y ~= 1400 m
_MAX_T = 100000.0


def _read_varints(buf, limit=None):
    """Decode unsigned LEB128 varints from buf. Stops quietly at truncation."""
    out = []
    append = out.append
    n = len(buf)
    p = 0
    while p < n:
        b = buf[p]
        p += 1
        if b < 0x80:
            append(b)
        else:
            v = b & 0x7F
            s = 7
            while True:
                if p >= n:
                    return out  # truncated varint: drop it
                b = buf[p]
                p += 1
                v |= (b & 0x7F) << s
                if b < 0x80:
                    break
                s += 7
                if s > 70:
                    return out  # garbage
            append(v)
        if limit is not None and len(out) >= limit:
            break
    return out


def _zz(v):
    return (v >> 1) ^ -(v & 1)


def _header_ok(data, p, n, last_t):
    if p < 1 or p + 9 > n or data[p - 1] != 0:
        return None
    t, flag, mtype, ln = _HDR.unpack_from(data, p)
    if not (t == t) or t < 0.0 or t > _MAX_T:  # NaN / out of range
        return None
    if p + 9 + ln > n:
        return None
    if last_t is not None and (t + 5.0 < last_t or t > last_t + 300.0):
        return None
    return t, flag, mtype, ln


def _chained(data, p, n, last_t):
    """Header at p is valid and is followed by another valid header (or EOF)."""
    h = _header_ok(data, p, n, last_t)
    if h is None:
        return None
    nxt = p + 10 + h[3]
    if nxt + 9 > n:
        return h if nxt >= n else None
    if _header_ok(data, nxt, n, h[0]) is None:
        return None
    return h


def iter_messages(data):
    """Yield (offset, time, flag, type, payload) for every framed message.

    Layout: [0x00][f32 time][u8 flag][u16 type][u16 len][payload] repeated,
    starting at offset 0. On a framing error it resyncs by scanning forward
    for a header that chains into a second valid header.
    """
    try:
        data = memoryview(data).tobytes() if not isinstance(data, bytes) else data
    except Exception:
        return
    n = len(data)
    p = 1
    last_t = None
    while p + 9 <= n:
        h = _chained(data, p, n, last_t)
        if h is None:
            p = _resync(data, p + 1, n, last_t)
            if p is None:
                return
            continue
        t, flag, mtype, ln = h
        yield p, t, flag, mtype, data[p + 9 : p + 9 + ln]
        last_t = t if last_t is None else max(last_t, t)
        p += 10 + ln


def _resync(data, p, n, last_t, max_scan=4 * 1024 * 1024):
    end = min(n - 9, p + max_scan)
    while p < end:
        q = data.find(b"\x00", p - 1, end)
        if q < 0:
            return None
        p = q + 1
        if _chained(data, p, n, last_t) is not None:
            return p
        p += 1
    return None


def parse_replay(data, include_lobby=False):
    """Return a dict with 'tracks' (keyed by full entity id when known),
    'id_map' (low index -> full id), 'frames' (frame counter -> time) and
    'stats' (message counts, skipped records)."""
    raw = {}
    id_map = {}
    frames = {}
    stats = {"messages": 0, "pos_messages": 0, "records": 0, "bad_messages": 0, "bad_records": 0}
    try:
        for _off, t, _flag, mtype, pl in iter_messages(data):
            stats["messages"] += 1
            if mtype == MSG_POSITIONS:
                stats["pos_messages"] += 1
                _parse_positions(pl, t, raw, frames, stats)
            elif mtype == MSG_ENTITY_STATE:
                _parse_state_ids(pl, id_map)
    except Exception:  # never raise on bad data
        pass

    tracks = {}
    for low, pts in raw.items():
        if id_map and low not in id_map:
            stats["dropped_unknown_ids"] = stats.get("dropped_unknown_ids", 0) + 1
            continue
        if not include_lobby:
            pts = [r for r in pts if r[2] < _LOBBY_MIN_Y]
        if not pts:
            continue
        pts.sort(key=lambda r: r[0])
        # drop exact duplicate timestamps (keep last)
        dedup = []
        for r in pts:
            if dedup and dedup[-1][0] == r[0]:
                dedup[-1] = r
            else:
                dedup.append(r)
        key = id_map.get(low, low)
        tracks.setdefault(key, []).extend(dedup)
    return {"tracks": tracks, "id_map": id_map, "frames": frames, "stats": stats}


def parse_tracks(data, include_lobby=False):
    """Map entity_id -> time-sorted [(t, x, y, z)] in seconds / metres.

    entity_id is the full 32-bit player id used in the .json (team slot in
    the top byte, player index in the low 24 bits) when the replay's state
    messages reveal it, otherwise the bare player index.
    Pre-match lobby samples (y >= 1000 m) are dropped unless include_lobby.
    """
    try:
        return parse_replay(data, include_lobby)["tracks"]
    except Exception:
        return {}


def _parse_positions(pl, t, raw, frames, stats):
    try:
        tk = _read_varints(pl)
    except Exception:
        stats["bad_messages"] += 1
        return
    if len(tk) < 2:
        stats["bad_messages"] += 1
        return
    count = _zz(tk[1])
    avail = (len(tk) - 2) // _REC_LEN
    if count < 0 or count > avail or len(tk) != 4 + _REC_LEN * count:
        stats["bad_messages"] += 1  # misaligned: records unreliable
        return
    frames.setdefault(tk[-1], t)
    for i in range(count):
        b = 2 + _REC_LEN * i
        low = tk[b]
        x = _zz(tk[b + 1]) / 1000.0
        y = _zz(tk[b + 2]) / 1000.0
        z = _zz(tk[b + 3]) / 1000.0
        if (
            low <= 0
            or low > 0xFFFFFF
            or not (t == t)
            or abs(x) > 5000
            or abs(y) > 5000
            or abs(z) > 5000
        ):
            stats["bad_records"] += 1
            continue
        raw.setdefault(low, []).append((float(t), x, y, z))
        stats["records"] += 1


def _parse_state_ids(pl, id_map):
    try:
        tk = _read_varints(pl)
    except Exception:
        return
    if not tk:
        return
    count = _zz(tk[0])
    if count <= 0 or len(tk) != 1 + _STATE_REC_LEN * count:
        return
    for i in range(count):
        full = tk[1 + _STATE_REC_LEN * i]
        low = full & 0xFFFFFF
        if 0 < low and 0 < (full >> 24) < 256 and low not in id_map:
            id_map[low] = full
