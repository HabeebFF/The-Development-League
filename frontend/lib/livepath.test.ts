import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { approach, boxOf, followStep, headAt, inView, lighten, settled, span, statusAt, upTo, viewFor, type TPoint, type View } from "./livepath.ts";

const walk: TPoint[] = [
  [10, 0, 0],
  [20, 100, 0],
  [30, 100, 50],
];

describe("live rotation path", () => {
  it("draws a path up to the moment shown, ending where the player is", () => {
    assert.deepEqual(upTo(walk, 5), []);
    assert.deepEqual(upTo(walk, 15), [
      [10, 0, 0],
      [15, 50, 0],
    ]);
    assert.deepEqual(upTo(walk, 99), walk);
  });

  it("knows where a path is, and nothing outside it", () => {
    assert.deepEqual(headAt([walk], 25), { x: 100, z: 25 });
    assert.equal(headAt([walk], 31), null);
    assert.equal(headAt([walk, [[40, 7, 7], [50, 8, 8]]], 35), null);
  });

  it("spans every path", () => {
    assert.deepEqual(span([[walk], [[[5, 0, 0], [6, 0, 0]]]]), [5, 30]);
    assert.deepEqual(span([]), [0, 0]);
  });

  it("lightens a team colour", () => {
    assert.equal(lighten("#ff0000", 0.5), "#ff8080");
    assert.equal(lighten("#000000", 0), "#000000");
    assert.equal(lighten("red", 0.5), "red");
  });
});

describe("camera follow", () => {
  const size = { w: 400, h: 200 };

  it("frames every player with room around them", () => {
    const box = boxOf(
      [
        { px: 100, py: 100 },
        { px: 140, py: 110 },
      ],
      20,
    )!;
    assert.deepEqual(box, { x: 100, y: 95, w: 40, h: 20, core: { x: 100, y: 100, w: 40, h: 10 } });
    const view = viewFor(box, size, 0.25);
    assert.ok(inView(box, view, size));
    // Centred: the box's middle is the screen's middle.
    assert.equal(120 * view.scale + view.x, 200);
    assert.equal(105 * view.scale + view.y, 100);
  });

  it("glides to the target without overshooting and settles there", () => {
    let v: View = { scale: 1, x: 0, y: 0 };
    const target = viewFor({ x: 500, y: 500, w: 50, h: 50 }, size);
    for (let i = 0; i < 200; i++) {
      const next = approach(v, target, 0.1, size);
      assert.ok(Math.abs(next.scale - target.scale) <= Math.abs(v.scale - target.scale) + 1e-9);
      v = next;
    }
    assert.ok(settled(v, target));
  });

  it("cuts straight to a player who appeared off screen", () => {
    const v: View = { scale: 1, x: 0, y: 0 };
    const box = boxOf([{ px: 5000, py: 5000 }], 50)!;
    const target = viewFor(box, size);
    assert.deepEqual(followStep(v, target, box, size, 1 / 60), target);
  });
});

describe("player status", () => {
  it("is knocked for a while after a knock, then out once dead and off the map", () => {
    assert.equal(statusAt(100, true, [], [95]), "knocked");
    assert.equal(statusAt(120, true, [], [95]), "ok"); // revived (or the logs lost it)
    assert.equal(statusAt(100, false, [98], [95]), "out");
    assert.equal(statusAt(100, true, [50], [40]), "ok"); // respawned after an early death
    assert.equal(statusAt(100, false, [], []), "ok"); // just a gap in the replay
  });
});
