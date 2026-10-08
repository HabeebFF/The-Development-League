// Map labels: shortening names and keeping labels from piling on top of each other.
// Pure maths, so it can be tested without a browser.

/** ``name`` cut to ``max`` characters with an ellipsis. */
export function shorten(name: string, max: number): string {
  const s = name.trim();
  return s.length <= max ? s : `${s.slice(0, Math.max(1, max - 1)).trimEnd()}…`;
}

/** Rough width of bold condensed text: good enough to size a pill before drawing it. */
export function textWidth(text: string, fontSize: number): number {
  let w = 0;
  for (const ch of text) w += /[A-Z0-9MW@]/.test(ch) ? 0.56 : /[il.,'|!\s]/.test(ch) ? 0.26 : 0.46;
  return w * fontSize;
}

/** A label to place: its dot (x, y), its size, and how much it matters (higher goes first). */
export type LabelItem = { id: string; x: number; y: number; w: number; h: number; rank: number };
/** Where a label went: its centre relative to its dot, and how much it was shrunk. */
export type Placed = { dx: number; dy: number; scale: number; crowded: boolean; hidden: boolean };

type Rect = { x0: number; y0: number; x1: number; y1: number };

const overlaps = (a: Rect, b: Rect) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;

/**
 * Places labels next to their dots without overlapping: above first, then the other sides,
 * then further out, then smaller. With nowhere left, a label of rank ``keep`` or more goes
 * above at its smallest, marked crowded (drawn fainter); any other label is hidden, since
 * its dot is still on the map. Important labels are placed first and keep the best spots.
 *
 * ``prev`` is where each label went last time (same units). A label keeps its last spot
 * while that spot is still clear, so labels don't swap sides from frame to frame as
 * players move; it only moves when something now covers it. A label pushed out to the
 * far ring comes back in as soon as a near spot frees up.
 */
export function layout(items: LabelItem[], gap: number, dot = 0, keep = 10, prev: Record<string, Placed> = {}): Record<string, Placed> {
  const out: Record<string, Placed> = {};
  const taken: Rect[] = items.map((i) => ({ x0: i.x - dot, y0: i.y - dot, x1: i.x + dot, y1: i.y + dot }));
  const order = [...items].sort((a, b) => b.rank - a.rank);
  for (const item of order) {
    let done: Placed | null = null;
    const last = prev[item.id];
    const free = (dx: number, dy: number, w: number, h: number) => {
      const r = { x0: item.x + dx - w / 2, y0: item.y + dy - h / 2, x1: item.x + dx + w / 2, y1: item.y + dy + h / 2 };
      if (taken.some((t) => overlaps(r, t))) return false;
      taken.push(r);
      return true;
    };
    for (const scale of [1, 0.85, 0.7]) {
      const w = item.w * scale;
      const h = item.h * scale;
      const near: [number, number][] = [
        [0, -(h / 2 + gap + dot)],
        [w / 2 + gap + dot, 0],
        [-(w / 2 + gap + dot), 0],
        [0, h / 2 + gap + dot],
        [w / 2 + gap, -(h / 2 + gap)],
        [-(w / 2 + gap), -(h / 2 + gap)],
        [w / 2 + gap, h / 2 + gap],
        [-(w / 2 + gap), h / 2 + gap],
      ];
      // A second ring further out; a leader line joins the label to its dot.
      const far = near.map(([x, y]): [number, number] => [x * 2, y * 2.4]);
      // Its last spot first, if it was this size and close in; a far one only after the near ring.
      const keepLast = last && !last.crowded && !last.hidden && last.scale === scale;
      const isNear = keepLast && near.some(([x, y]) => Math.abs(x - last.dx) < 0.5 && Math.abs(y - last.dy) < 0.5);
      const sides: [number, number][] = [
        ...(isNear ? [[last.dx, last.dy] as [number, number]] : []),
        ...near,
        ...(keepLast && !isNear ? [[last.dx, last.dy] as [number, number]] : []),
        ...far,
      ];
      for (const [dx, dy] of sides) {
        if (free(dx, dy, w, h)) {
          done = { dx, dy, scale, crowded: false, hidden: false };
          break;
        }
      }
      if (done) break;
    }
    if (!done) {
      const scale = 0.7;
      const hidden = item.rank < keep;
      done = { dx: 0, dy: -((item.h * scale) / 2 + gap + dot), scale, crowded: true, hidden };
    }
    out[item.id] = done;
  }
  return out;
}
