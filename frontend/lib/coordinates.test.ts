import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { anchorsFor, fitBounds, then, toPixel, toWorld, type Transform } from "./coordinates.ts";

const T: Transform = { a: 0.85, b: 0, c: 512, d: 0, e: -0.85, f: 512 };

describe("coordinates", () => {
  it("round-trips world and pixels", () => {
    const { px, py } = toPixel(T, 123, -45);
    const back = toWorld(T, px, py);
    assert.ok(Math.abs(back.x - 123) < 1e-9 && Math.abs(back.z + 45) < 1e-9);
  });

  it("composes with a pixel-space move and zoom", () => {
    const zoom: Transform = { a: 2, b: 0, c: 10, d: 0, e: 2, f: -5 };
    const both = then(T, zoom);
    const direct = toPixel(zoom, toPixel(T, 50, 60).px, toPixel(T, 50, 60).py);
    assert.deepEqual(toPixel(both, 50, 60), direct);
  });

  it("fits points into a canvas with world z pointing up", () => {
    const t = fitBounds([{ x: -500, z: -500 }, { x: 500, z: 500 }], 1000, 1000, 0);
    assert.deepEqual(toPixel(t, -500, 500), { px: 0, py: 0 });
    assert.deepEqual(toPixel(t, 500, -500), { px: 1000, py: 1000 });
  });

  it("makes anchors that reproduce the transform", () => {
    const anchors = anchorsFor(T, [{ x: -400, z: -400 }, { x: 400, z: 400 }]);
    assert.deepEqual(anchors[0], { world_x: -400, world_z: -400, pixel_x: 172, pixel_y: 852 });
  });
});
