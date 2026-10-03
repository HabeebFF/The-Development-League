// Rotation playback and camera follow: pure maths, so it can be tested without a browser.

/** A point on a path: game seconds, world x, world z. */
export type TPoint = [number, number, number];
export type World = { x: number; z: number };
/** A rectangle in content pixels. ``core`` is the tight box around the points themselves. */
export type Box = { x: number; y: number; w: number; h: number; core?: Box };
/** How the map is shown: content pixel (x, y) lands at screen (x + cx*scale, ...). */
export type View = { scale: number; x: number; y: number };
export type Size = { w: number; h: number };

/** The part of a path walked by time t, ending exactly where the player is at t. */
export function upTo(seg: TPoint[], t: number): TPoint[] {
  if (!seg.length || seg[0][0] > t) return [];
  if (seg[seg.length - 1][0] <= t) return seg;
  const out: TPoint[] = [];
  for (let i = 0; i < seg.length; i++) {
    const p = seg[i];
    if (p[0] <= t) {
      out.push(p);
      continue;
    }
    const a = seg[i - 1];
    const k = p[0] === a[0] ? 0 : (t - a[0]) / (p[0] - a[0]);
    out.push([t, a[1] + (p[1] - a[1]) * k, a[2] + (p[2] - a[2]) * k]);
    break;
  }
  return out;
}

/** Where a path is at t, or null outside its segments (not landed yet, a gap, dead). */
export function headAt(segments: TPoint[][], t: number): World | null {
  for (const seg of segments) {
    if (!seg.length || t < seg[0][0] || t > seg[seg.length - 1][0]) continue;
    const walked = upTo(seg, t);
    const p = walked[walked.length - 1];
    return { x: p[1], z: p[2] };
  }
  return null;
}

/** First and last time over a set of paths ([0, 0] when there are none). */
export function span(paths: TPoint[][][]): [number, number] {
  let lo = Infinity;
  let hi = -Infinity;
  for (const segments of paths)
    for (const seg of segments) {
      if (!seg.length) continue;
      lo = Math.min(lo, seg[0][0]);
      hi = Math.max(hi, seg[seg.length - 1][0]);
    }
  return Number.isFinite(lo) ? [lo, hi] : [0, 0];
}

/** ``hex`` mixed towards white by ``k`` (0 = unchanged, 1 = white). */
export function lighten(hex: string, k: number): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  const mix = (c: number) => Math.round(c + (255 - c) * k);
  const [r, g, b] = [mix(n >> 16), mix((n >> 8) & 255), mix(n & 255)];
  return `#${((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1)}`;
}

/** The box around some pixel points, grown to at least ``min`` on each side. */
export function boxOf(points: { px: number; py: number }[], min: number): Box | null {
  if (!points.length) return null;
  const xs = points.map((p) => p.px);
  const ys = points.map((p) => p.py);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const w = Math.max(min, x1 - x0);
  const h = Math.max(min, y1 - y0);
  const core = { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
  return { x: (x0 + x1) / 2 - w / 2, y: (y0 + y1) / 2 - h / 2, w, h, core };
}

/** The view that centres ``box`` with ``pad`` (a fraction) of room around it. */
export function viewFor(box: Box, size: Size, pad = 0.35, maxScale = 12): View {
  const scale = Math.min(maxScale, size.w / (box.w * (1 + 2 * pad)), size.h / (box.h * (1 + 2 * pad)));
  const cx = box.x + box.w / 2;
  const cy = box.y + box.h / 2;
  return { scale, x: size.w / 2 - cx * scale, y: size.h / 2 - cy * scale };
}

/** True when all of ``box`` is on screen in ``view``. */
export function inView(box: Box, view: View, size: Size): boolean {
  const left = box.x * view.scale + view.x;
  const top = box.y * view.scale + view.y;
  return left >= 0 && top >= 0 && left + box.w * view.scale <= size.w && top + box.h * view.scale <= size.h;
}

/**
 * One step of a smooth camera move from ``from`` to ``to``: ``k`` of the way, measured on
 * the centre and on the zoom (log scale), so the camera glides instead of swinging.
 */
export function approach(from: View, to: View, k: number, size: Size): View {
  const centre = (v: View) => ({ cx: (size.w / 2 - v.x) / v.scale, cy: (size.h / 2 - v.y) / v.scale });
  const a = centre(from);
  const b = centre(to);
  const scale = Math.exp(Math.log(from.scale) + (Math.log(to.scale) - Math.log(from.scale)) * k);
  const cx = a.cx + (b.cx - a.cx) * k;
  const cy = a.cy + (b.cy - a.cy) * k;
  return { scale, x: size.w / 2 - cx * scale, y: size.h / 2 - cy * scale };
}

/** Close enough that moving further wouldn't show. */
export function settled(a: View, b: View): boolean {
  return Math.abs(a.x - b.x) < 0.5 && Math.abs(a.y - b.y) < 0.5 && Math.abs(a.scale / b.scale - 1) < 0.002;
}

/** How long a knocked player counts as down when the logs don't say they were revived. */
export const KNOCK_S = 15;

/** A player's state at t: on their feet, knocked, or out (dead and not back on the map). */
export function statusAt(t: number, onMap: boolean, deaths: number[], knocks: number[]): "ok" | "knocked" | "out" {
  if (!onMap) return deaths.some((d) => d <= t) ? "out" : "ok";
  const knock = knocks.filter((k) => k <= t).pop();
  if (knock == null || t - knock > KNOCK_S) return "ok";
  return deaths.some((d) => d >= knock && d <= t) ? "ok" : "knocked";
}

/**
 * How far the camera moves towards ``target`` this frame: a gentle glide normally, faster
 * once the framed area starts slipping off screen, and a cut when a player is already off
 * screen (a respawn drop far away), so a followed team is never out of frame.
 */
export function followStep(view: View, target: View, box: Box, size: Size, dt: number): View {
  if (box.core && !inView(box.core, view, size)) return target;
  const rate = inView(box, view, size) ? 5 : 30;
  return approach(view, target, 1 - Math.exp(-dt * rate), size);
}
