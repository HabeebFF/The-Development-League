import assert from "node:assert/strict";
import { test } from "node:test";

import { byFixture, closesIn, coins, percent, profit, signedCoins, stakeProblem, totalReturn, type Market } from "./predictions.ts";

test("return and profit match the server's rounding down", () => {
  assert.equal(totalReturn(100, "2.50"), 250);
  assert.equal(profit(100, "2.50"), 150);
  assert.equal(totalReturn(33, "1.55"), 51); // 51.15
  assert.equal(totalReturn(10, "1.01"), 10); // 10.1
  assert.equal(totalReturn(7, "3.3"), 23); // 23.1
  assert.equal(totalReturn(500, "1000.00"), 500000);
  assert.equal(totalReturn(29, "1.15"), 33); // floats would give 33.349999...
});

test("stake checks", () => {
  assert.equal(stakeProblem("100", 1000), null);
  assert.equal(stakeProblem("", 1000), "Enter a whole number of coins.");
  assert.equal(stakeProblem("10.5", 1000), "Enter a whole number of coins.");
  assert.equal(stakeProblem("-5", 1000), "Enter a whole number of coins.");
  assert.equal(stakeProblem("9", 1000), "The smallest stake is 10 coins.");
  assert.equal(stakeProblem("501", 1000), "The biggest stake is 500 coins.");
  assert.equal(stakeProblem("300", 200), "You only have 200 coins.");
  assert.equal(stakeProblem("300", null), null);
});

test("closing countdown", () => {
  const now = Date.parse("2026-10-16T18:00:00Z");
  assert.equal(closesIn("2026-10-16T20:05:00Z", now), "Closes in 2h 05m");
  assert.equal(closesIn("2026-10-16T18:45:00Z", now), "Closes in 45m");
  assert.equal(closesIn("2026-10-16T18:00:30Z", now), "Closes in 30s");
  assert.equal(closesIn("2026-10-18T19:00:00Z", now), "Closes in 2d 1h");
  assert.equal(closesIn("2026-10-16T17:00:00Z", now), "Closed");
});

test("numbers read plainly", () => {
  assert.equal(coins(1), "1 coin");
  assert.equal(coins(1500), "1,500 coins");
  assert.equal(signedCoins(250), "+250");
  assert.equal(signedCoins(-100), "−100");
  assert.equal(percent(0.6667), "66.7%");
  assert.equal(percent(null), "–");
});

test("markets group under their fixture", () => {
  const m = (id: number, fixture: number | null) =>
    ({ id, season: { id: 1, name: "Season 1" }, fixture: fixture ? { id: fixture, title: `F${fixture}` } : null }) as Market;
  assert.deepEqual(
    byFixture([m(1, 7), m(2, 7), m(3, null), m(4, 8)]).map((g) => [g.title, g.markets.map((x) => x.id)]),
    [
      ["F7", [1, 2]],
      ["Season 1", [3]],
      ["F8", [4]],
    ],
  );
});
