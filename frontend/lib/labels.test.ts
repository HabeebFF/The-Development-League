import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { layout, shorten, textWidth } from "./labels.ts";

describe("map labels", () => {
  it("shortens long names with an ellipsis", () => {
    assert.equal(shorten("NB JAY", 10), "NB JAY");
    assert.equal(shorten("SUPERLONGPLAYERNAME", 8), "SUPERLO…");
  });

  it("measures wide letters wider than narrow ones", () => {
    assert.ok(textWidth("MMMM", 10) > textWidth("iiii", 10));
  });

  it("sits a lone label above its dot", () => {
    const placed = layout([{ id: "a", x: 0, y: 0, w: 40, h: 20, rank: 0 }], 2);
    assert.deepEqual(placed.a, { dx: 0, dy: -12, scale: 1, crowded: false, hidden: false });
  });

  it("nudges labels of nearby dots apart instead of stacking them", () => {
    const items = [0, 1, 2, 3].map((i) => ({ id: `p${i}`, x: i * 4, y: 0, w: 40, h: 20, rank: i === 2 ? 5 : 0 }));
    const placed = layout(items, 2, 3);
    const rects = items.map((i) => {
      const p = placed[i.id];
      const [w, h] = [i.w * p.scale, i.h * p.scale];
      return { x0: i.x + p.dx - w / 2, x1: i.x + p.dx + w / 2, y0: i.y + p.dy - h / 2, y1: i.y + p.dy + h / 2, crowded: p.crowded };
    });
    const clear = rects.filter((r) => !r.crowded);
    for (const a of clear)
      for (const b of clear) if (a !== b) assert.ok(!(a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1));
    // The most important label keeps the spot right above its dot.
    assert.deepEqual(placed.p2, { dx: 0, dy: -15, scale: 1, crowded: false, hidden: false });
  });

  it("hides labels with no room left, but keeps important ones", () => {
    const items = Array.from({ length: 60 }, (_, i) => ({ id: `p${i}`, x: 0, y: 0, w: 40, h: 20, rank: i === 59 ? 10 : 0 }));
    const placed = layout(items, 2, 3);
    assert.ok(Object.values(placed).some((p) => p.hidden));
    assert.equal(placed.p59.hidden, false);
  });
});
