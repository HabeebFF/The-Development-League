import assert from "node:assert/strict";
import { test } from "node:test";

import { breakdown, dc, kingMonth, nextRank, rankFor, teamCoin } from "./dc.ts";

test("lists what a match paid for", () => {
  assert.equal(breakdown({ kills: 3, booyah: true, mvp: true }), "3 kills · Booyah · MVP");
  assert.equal(breakdown({ kills: 1, booyah: false, mvp: false }), "1 kill");
  assert.equal(breakdown({ kills: 0, booyah: false, mvp: false }), "played");
});

test("formats DC", () => {
  assert.equal(dc(12400), "12,400 DC");
});

const STEPS = [
  { key: "silver", name: "Silver", min: 25_000 },
  { key: "bronze", name: "Bronze", min: 5_000 },
];

test("rank from earned DC", () => {
  assert.equal(rankFor(4_999, STEPS), null);
  assert.equal(rankFor(5_000, STEPS)?.key, "bronze");
  assert.equal(rankFor(30_000, STEPS)?.key, "silver");
  assert.deepEqual(nextRank(6_000, STEPS), { step: STEPS[0], need: 19_000 });
  assert.equal(nextRank(30_000, STEPS), null);
});

test("king month and team coins", () => {
  assert.equal(kingMonth("2026-11-01"), "NOVEMBER");
  const teams = [1, 2, 3, 4].map((id) => ({ team_id: id, name: `T${id}`, slug: `t${id}`, dc: 100 - id }));
  assert.equal(teamCoin(teams, 2), 2);
  assert.equal(teamCoin(teams, 4), null);
  assert.equal(teamCoin(teams, null), null);
});
