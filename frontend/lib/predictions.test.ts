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

test("staff: outcome codes, titles and checks", async () => {
  const { outcomeCodes, defaultTitle, teamsProblem, oddsProblem } = await import("./predictions.ts");
  const teams = [
    { id: 1, name: "Alpha" },
    { id: 2, name: "Bravo" },
  ];
  assert.deepEqual(outcomeCodes("H2H_KILLS", teams).map((o) => o.code), ["team:1", "team:2"]);
  assert.deepEqual(outcomeCodes("TOP_N", teams.slice(0, 1), 5).map((o) => o.label), ["Yes, Alpha top 5", "No, Alpha outside top 5"]);
  assert.equal(defaultTitle("H2H_PLACEMENT", teams, 3, 2), "Alpha v Bravo: finishes higher · Match 2");
  assert.equal(defaultTitle("BOOYAH", teams), "Booyah");
  assert.equal(teamsProblem("BOOYAH", 1), "Pick at least 2 teams.");
  assert.equal(teamsProblem("H2H_KILLS", 3), "Pick exactly 2 teams.");
  assert.equal(teamsProblem("TOP_N", 1), null);
  assert.deepEqual(outcomeCodes("TEAM_KILLS", teams.slice(0, 1), 3, 10).map((o) => o.label), ["Alpha: 10 or more kills", "Alpha: 9 or fewer kills"]);
  assert.deepEqual(outcomeCodes("OVERALL_TOP_N", teams.slice(0, 1), 5).map((o) => o.code), ["yes", "no"]);
  assert.equal(defaultTitle("TEAM_KILLS", teams, 3, 1, 12), "Alpha: 12+ kills · Match 1");
  assert.equal(teamsProblem("SESSION_WINNER", 1), "Pick at least 2 teams.");
  for (const bad of ["0", "1.00", "-2", "2.555", "abc", "1000.01", ""]) assert.ok(oddsProblem(bad), bad);
  for (const good of ["1.01", "2.5", "1000", "15.00"]) assert.equal(oddsProblem(good), null, good);
});

test("staff: market types per fixture and kills lines", async () => {
  const { categoriesFor, lineProblem } = await import("./predictions.ts");
  assert.deepEqual(categoriesFor("session").map((c) => c.key), ["SESSION_WINNER", "MOST_BOOYAHS"]);
  assert.deepEqual(categoriesFor("season").map((c) => c.key), ["OVERALL_WINNER", "OVERALL_TOP_N"]);
  assert.ok(categoriesFor("match").some((c) => c.key === "TEAM_KILLS"));
  assert.equal(lineProblem("10"), null);
  assert.equal(lineProblem("0"), "A whole number from 1 to 60.");
  assert.equal(lineProblem("61"), "A whole number from 1 to 60.");
  assert.equal(lineProblem("9.5"), "A whole number from 1 to 60.");
});
