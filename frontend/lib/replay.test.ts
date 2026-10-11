import assert from "node:assert/strict";
import { describe, it, test } from "node:test";

import {
  clock,
  enemiesInScan,
  killsAt,
  positionAt,
  replayHref,
  replayStart,
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

test("enemiesInScan counts other teams inside the circle when it fires", () => {
  const scan: ReplayObject = {
    kind: "DINOCULARS", owner: 1, owner_name: "A", team: "a",
    start_s: 0, end_s: 3, x: 0, z: 0, radius: 50, points: [],
  };
  const at = (entity_id: number, team: string, x: number): ReplayPlayer => ({
    entity_id, name: "", team, start_s: 0, points: [[x * 10, 0]],
  });
  const players = [at(1, "a", 0), at(2, "a", 10), at(3, "b", 49), at(4, "b", 51), at(5, "c", -20)];
  assert.equal(enemiesInScan(scan, players, 0.5), 2); // 3 and 5; not teammates, not 51 m away
});

describe("watch-this links", () => {
  it("reads a start time and team, ignoring junk", () => {
    assert.deepEqual(replayStart({ t: "142", team: "noobz-esports" }), { startAt: 142, team: "noobz-esports" });
    assert.deepEqual(replayStart({ t: "-3", team: "<b>" }), { startAt: undefined, team: undefined });
    assert.deepEqual(replayStart({}), { startAt: undefined, team: undefined });
  });

  it("builds the link", () => {
    assert.equal(replayHref("/team/matches/7/replay", 141.6, "alpha"), "/team/matches/7/replay?t=142&team=alpha");
    assert.equal(replayHref("/matches/7/replay", -5), "/matches/7/replay?t=0");
  });
});

test("kills count up as the replay plays, without knocks or self-kills", () => {
  const e = (kind: "KILL" | "KNOCK", t: number, actor: number, target: number) =>
    ({ kind, t, actor, target, headshot: null, x: null, z: null, tx: null, tz: null }) as const;
  const events = [e("KNOCK", 10, 1, 2), e("KILL", 12, 1, 2), e("KILL", 30, 1, 3), e("KILL", 40, 4, 4)];
  assert.deepEqual(killsAt(events, 5), {});
  assert.deepEqual(killsAt(events, 12), { 1: 1 });
  assert.deepEqual(killsAt(events, 60), { 1: 2 });
});
