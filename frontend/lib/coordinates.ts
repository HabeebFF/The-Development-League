// World (x, z) <-> image pixels. Same maths as backend/apps/maps/calibration.py.
//   px = a*x + b*z + c
//   py = d*x + e*z + f

export type Transform = { a: number; b: number; c: number; d: number; e: number; f: number };
export type WorldPoint = { x: number; z: number };
export type PixelPoint = { px: number; py: number };
export type Anchor = { world_x: number; world_z: number; pixel_x: number; pixel_y: number };

export function toPixel(t: Transform, x: number, z: number): PixelPoint {
  return { px: t.a * x + t.b * z + t.c, py: t.d * x + t.e * z + t.f };
}

export function toWorld(t: Transform, px: number, py: number): WorldPoint {
  const det = t.a * t.e - t.b * t.d;
  if (Math.abs(det) < 1e-12) throw new Error("Transform can't be inverted");
  const u = px - t.c;
  const v = py - t.f;
  return { x: (t.e * u - t.b * v) / det, z: (-t.d * u + t.a * v) / det };
}

/** Compose: first `inner`, then an affine map on pixels (used by the overlay tool). */
export function then(inner: Transform, outer: Transform): Transform {
  return {
    a: outer.a * inner.a + outer.b * inner.d,
    b: outer.a * inner.b + outer.b * inner.e,
    c: outer.a * inner.c + outer.b * inner.f + outer.c,
    d: outer.d * inner.a + outer.e * inner.d,
    e: outer.d * inner.b + outer.e * inner.e,
    f: outer.d * inner.c + outer.e * inner.f + outer.f,
  };
}

/**
 * A transform that fits the given world points into a width x height canvas, used
 * before a map has an image or calibration. Image y points down, world z points up.
 */
export function fitBounds(
  points: WorldPoint[],
  width: number,
  height: number,
  margin = 40,
): Transform {
  const xs = points.map((p) => p.x);
  const zs = points.map((p) => p.z);
  const minX = xs.length ? Math.min(...xs) : -600;
  const maxX = xs.length ? Math.max(...xs) : 600;
  const minZ = zs.length ? Math.min(...zs) : -600;
  const maxZ = zs.length ? Math.max(...zs) : 600;
  const span = Math.max(maxX - minX, maxZ - minZ, 100);
  const scale = (Math.min(width, height) - 2 * margin) / span;
  const cx = (minX + maxX) / 2;
  const cz = (minZ + maxZ) / 2;
  return { a: scale, b: 0, c: width / 2 - scale * cx, d: 0, e: -scale, f: height / 2 + scale * cz };
}

/** Three anchors that pin a transform down exactly (the overlay tool saves these). */
export function anchorsFor(t: Transform, world: WorldPoint[]): Anchor[] {
  return world.map(({ x, z }) => {
    const { px, py } = toPixel(t, x, z);
    return { world_x: round(x), world_z: round(z), pixel_x: round(px), pixel_y: round(py) };
  });
}

function round(v: number): number {
  return Math.round(v * 100) / 100;
}
