import assert from "node:assert/strict";
import { test } from "node:test";

import {
  clock,
  positionAt,
  strikesAt,
  timeRange,
  trailAt,
  uavAt,
  zoneAt,
  type ReplayObject,
  type ReplayPlayer,
} from "./replay.ts";
import type { Zone } from "./api.ts";

const p: ReplayPlayer = {
  entity_id: 1,
  name: "A",
  team: "t",
  start_s: 60,
  points: [[0, 0], [10, 20], null, [100, 100]],
};

test("positionAt interpolates and respects gaps", () => {
  assert.deepEqual(positionAt(p, 0.5, 60), { x: 0, z: 0 });
  assert.deepEqual(positionAt(p, 0.5, 60.25), { x: 0.5, z: 1 });
  assert.equal(positionAt(p, 0.5, 61), null);
  assert.deepEqual(positionAt(p, 0.5, 61.5), { x: 10, z: 10 });
  assert.equal(positionAt(p, 0.5, 59), null);
  assert.equal(positionAt(p, 0.5, 70), null);
});

test("trailAt splits at gaps", () => {
  const pieces = trailAt(p, 0.5, 61.5, 10);
  assert.equal(pieces.length, 2);
  assert.deepEqual(pieces[1][0], { x: 10, z: 10 });
  assert.deepEqual(pieces[0][0], { x: 0, z: 0 });
  assert.deepEqual(timeRange([p], 0.5), [60, 61.5]);
});

test("zoneAt shrinks between phases", () => {
  const base = { outer_x: 0, outer_z: 0, inner_x: 100, inner_z: 0, stage_index: 1 };
  const zones: Zone[] = [
    { ...base, state: "STABLE", game_time_s: 100, outer_radius: 500, inner_radius: 300 },
    { ...base, state: "SHRINK", game_time_s: 200, outer_radius: 500, inner_radius: 300 },
    { ...base, stage_index: 2, state: "STABLE", game_time_s: 300, outer_radius: 300, inner_radius: 150 },
  ];
  assert.equal(zoneAt(zones, 50).current, null);
  assert.deepEqual(zoneAt(zones, 150).current, { x: 0, z: 0, r: 500 });
  assert.deepEqual(zoneAt(zones, 250).current, { x: 50, z: 0, r: 400 });
  assert.equal(zoneAt(zones, 350).next?.r, 150);
  assert.equal(clock(125.9), "2:05");
});

test("uavAt interpolates, holds while hovering, and ends", () => {
  const o: ReplayObject = {
    kind: "GENERAL_UAV", owner: null, owner_name: null, team: null,
    start_s: 100, end_s: 200, x: 0, z: 0, radius: null,
    points: [[100, 0, 0], [101, 100, 0], [190, 100, 500], [191, 200, 500]],
  };
  assert.deepEqual(uavAt(o, 100.5), { x: 5, z: 0 });
  assert.deepEqual(uavAt(o, 150), { x: 10, z: 0 }); // hovering: no samples, stays put
  assert.deepEqual(uavAt(o, 190.5), { x: 15, z: 50 });
  assert.equal(uavAt(o, 99), null);
  assert.equal(uavAt(o, 201), null);
  const bolt: ReplayObject = { ...o, kind: "BOLT_MAKER", points: [[100, 10, 10], [102, 20, 20]] };
  assert.equal(strikesAt(bolt, 101).length, 1);
  assert.equal(strikesAt(bolt, 102.5)[0].x, 2);
});
