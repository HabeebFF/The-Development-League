"""World <-> image coordinates for a map (pure Python, no Django).

A transform is an affine map from game world (x, z) to image pixels (px, py):

    px = a*x + b*z + c
    py = d*x + e*z + f

- 2 points: the image is assumed square to the world axes, so each axis gets its own
  scale and offset (either may be negative, which covers flipped axes).
- 3 or more points: a least-squares affine fit, which also handles rotation and skew.

The fit error (RMS pixel distance between where points were clicked and where the
transform puts them) makes a bad click obvious.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

MIN_SPREAD = 1.0  # world units / pixels; two points closer than this can't calibrate


class CalibrationError(ValueError):
    """The points can't define a transform (too few, or all on one line)."""


@dataclass(frozen=True)
class Point:
    world_x: float
    world_z: float
    pixel_x: float
    pixel_y: float


@dataclass(frozen=True)
class Transform:
    a: float
    b: float
    c: float
    d: float
    e: float
    f: float

    def to_pixel(self, x: float, z: float) -> tuple[float, float]:
        return (self.a * x + self.b * z + self.c, self.d * x + self.e * z + self.f)

    def to_world(self, px: float, py: float) -> tuple[float, float]:
        det = self.a * self.e - self.b * self.d
        if abs(det) < 1e-12:
            raise CalibrationError("Transform can't be inverted.")
        u, v = px - self.c, py - self.f
        return ((self.e * u - self.b * v) / det, (-self.d * u + self.a * v) / det)

    def as_dict(self) -> dict[str, float]:
        return {k: round(getattr(self, k), 9) for k in "abcdef"}

    @classmethod
    def from_dict(cls, data: dict) -> Transform:
        return cls(**{k: float(data[k]) for k in "abcdef"})


@dataclass(frozen=True)
class Fit:
    transform: Transform
    residuals: list[float]  # pixel distance per point, same order as given

    @property
    def rms_error(self) -> float:
        return math.sqrt(sum(r * r for r in self.residuals) / len(self.residuals))


def fit(points: list[Point]) -> Fit:
    if len(points) < 2:
        raise CalibrationError("At least 2 points are needed.")
    transform = _fit_axes(points) if len(points) == 2 else _fit_affine(points)
    residuals = []
    for p in points:
        px, py = transform.to_pixel(p.world_x, p.world_z)
        residuals.append(math.hypot(px - p.pixel_x, py - p.pixel_y))
    return Fit(transform, residuals)


def _fit_axes(points: list[Point]) -> Transform:
    p, q = points
    dx, dz = q.world_x - p.world_x, q.world_z - p.world_z
    if abs(dx) < MIN_SPREAD or abs(dz) < MIN_SPREAD:
        raise CalibrationError("With 2 points, pick spots far apart both left-right and up-down.")
    a = (q.pixel_x - p.pixel_x) / dx
    e = (q.pixel_y - p.pixel_y) / dz
    return Transform(a, 0.0, p.pixel_x - a * p.world_x, 0.0, e, p.pixel_y - e * p.world_z)


def _fit_affine(points: list[Point]) -> Transform:
    # Normal equations for rows [x, z, 1]; the same matrix serves both outputs.
    rows = [(p.world_x, p.world_z, 1.0) for p in points]
    m = [[sum(r[i] * r[j] for r in rows) for j in range(3)] for i in range(3)]
    bx = [sum(r[i] * p.pixel_x for r, p in zip(rows, points, strict=True)) for i in range(3)]
    by = [sum(r[i] * p.pixel_y for r, p in zip(rows, points, strict=True)) for i in range(3)]
    a, b, c = _solve3(m, bx)
    d, e, f = _solve3(m, by)
    return Transform(a, b, c, d, e, f)


def _solve3(m: list[list[float]], v: list[float]) -> tuple[float, float, float]:
    det = _det3(m)
    scale = max(abs(x) for row in m for x in row) or 1.0
    if abs(det) <= 1e-9 * scale**3:
        raise CalibrationError("The points are all on one line; spread them out.")
    out = []
    for col in range(3):
        mc = [[v[r] if c == col else m[r][c] for c in range(3)] for r in range(3)]
        out.append(_det3(mc) / det)
    return out[0], out[1], out[2]


def _det3(m: list[list[float]]) -> float:
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def point_in_polygon(x: float, z: float, polygon: list[list[float]]) -> bool:
    """Ray casting; polygon is [[x, z], ...] in world coordinates."""
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, z1 = polygon[i]
        x2, z2 = polygon[(i + 1) % n]
        if (z1 > z) != (z2 > z):
            cross = x1 + (z - z1) * (x2 - x1) / (z2 - z1)
            if x < cross:
                inside = not inside
    return inside


def polygon_centre(polygon: list[list[float]]) -> tuple[float, float]:
    """Area-weighted centroid (falls back to the vertex mean for degenerate shapes)."""
    area = cx = cz = 0.0
    n = len(polygon)
    for i in range(n):
        x1, z1 = polygon[i]
        x2, z2 = polygon[(i + 1) % n]
        cross = x1 * z2 - x2 * z1
        area += cross
        cx += (x1 + x2) * cross
        cz += (z1 + z2) * cross
    if abs(area) < 1e-9:
        return (sum(p[0] for p in polygon) / n, sum(p[1] for p in polygon) / n)
    return (cx / (3 * area), cz / (3 * area))
