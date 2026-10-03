import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  copyLast,
  movePoint,
  nextCheckpoint,
  placePoint,
  removePoint,
  routeLines,
  type RotationPoint,
} from "./rotation.ts";

const auto = (checkpoint: RotationPoint["checkpoint"], x: number, z: number): RotationPoint => ({
  checkpoint,
  x,
  z,
  game_time_s: 100,
  source: "AUTO",
  evidence: { kills: 2 },
  note: "",
});

const order = (points: RotationPoint[]) => points.map((p) => p.checkpoint);

describe("plotting", () => {
  it("replaces single checkpoints and keeps checkpoint order", () => {
    let points = [auto("ZONE_1", 1, 1), auto("FINAL", 9, 9)];
    points = placePoint(points, "DROP", 0.123, 5);
    points = placePoint(points, "ZONE_1", 2, 2);
    assert.deepEqual(order(points), ["DROP", "ZONE_1", "FINAL"]);
    assert.deepEqual(points[0], {
      checkpoint: "DROP",
      x: 0.12,
      z: 5,
      game_time_s: null,
      source: "MANUAL",
      note: "",
    });
    assert.equal(points[1].x, 2);
  });

  it("final and eliminated exclude each other; extras add up", () => {
    let points = placePoint([auto("FINAL", 1, 1)], "ELIMINATED", 2, 2);
    points = placePoint(points, "EXTRA", 3, 3);
    points = placePoint(points, "EXTRA", 4, 4);
    assert.deepEqual(order(points), ["EXTRA", "EXTRA", "ELIMINATED"]);
    assert.deepEqual(
      points.map((p) => p.x),
      [3, 4, 2],
    );
  });

  it("moving a point makes it manual; removing drops it", () => {
    const moved = movePoint([auto("ZONE_1", 1, 1)], 0, 5, 6);
    assert.equal(moved[0].source, "MANUAL");
    assert.deepEqual(moved[0].evidence, {});
    assert.equal(removePoint(moved, 0).length, 0);
  });

  it("copies the previous position and suggests the next checkpoint", () => {
    let points = placePoint([], "DROP", 10, 20);
    assert.equal(nextCheckpoint(points, 3), "ZONE_1");
    points = copyLast(points, "ZONE_1");
    assert.deepEqual([points[1].x, points[1].z], [10, 20]);
    assert.equal(copyLast([], "ZONE_1").length, 0);
    points = placePoint(points, "ZONE_2", 1, 1);
    points = placePoint(points, "ZONE_3", 1, 1);
    assert.equal(nextCheckpoint(points, 3), null);
  });
});

describe("routeLines", () => {
  const t = { a: 1, b: 0, c: 0, d: 0, e: 1, f: 0 };
  const pts: RotationPoint[] = [
    { checkpoint: "DROP", x: 0, z: 0, game_time_s: null, source: "AUTO" } as RotationPoint,
    { checkpoint: "EXTRA", x: 5, z: 5, game_time_s: null, source: "AUTO" } as RotationPoint,
    { checkpoint: "ZONE_1", x: 10, z: 0, game_time_s: null, source: "AUTO" } as RotationPoint,
  ];

  it("follows the replay path, one line per segment", () => {
    const path: [number, number, number][][] = [
      [
        [0, 0, 0],
        [1, 2, 3],
        [2, 4, 1],
      ],
      [[9, 7, 7]], // a lone point draws nothing
      [
        [20, 8, 8],
        [21, 9, 9],
      ],
    ];
    assert.deepEqual(routeLines(pts, path, t), [
      [0, 0, 2, 3, 4, 1],
      [8, 8, 9, 9],
    ]);
  });

  it("joins the checkpoints without a path, skipping extras", () => {
    assert.deepEqual(routeLines(pts, [], t), [[0, 0, 10, 0]]);
    assert.deepEqual(routeLines(pts, undefined, t), [[0, 0, 10, 0]]);
  });
});
