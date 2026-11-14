import assert from "node:assert/strict";
import { test } from "node:test";

import { multiplier, ordinal, podium, profit } from "./fanZone.ts";

test("odds read as a short multiplier", () => {
  assert.equal(multiplier("12.50"), "×12.5");
  assert.equal(multiplier("2.00"), "×2");
  assert.equal(multiplier("3.25"), "×3.25");
  assert.equal(multiplier("odd"), "odd");
});

test("profit is payout minus stake, never below zero", () => {
  assert.equal(profit({ stake: 100, payout: 1250 }), 1150);
  assert.equal(profit({ stake: 100, payout: 0 }), 0);
});

test("ordinals", () => {
  assert.deepEqual([1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 101, 111].map(ordinal), ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "23rd", "101st", "111th"]);
});

test("podium shows 2nd, 1st, 3rd and skips missing places", () => {
  assert.deepEqual(podium([{ rank: 1 }, { rank: 2 }, { rank: 3 }]).map((f) => f.rank), [2, 1, 3]);
  assert.deepEqual(podium([{ rank: 1 }]).map((f) => f.rank), [1]);
  assert.deepEqual(podium([{ rank: 1 }, { rank: 2 }]).map((f) => f.rank), [2, 1]);
});
