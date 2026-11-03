import assert from "node:assert/strict";
import test from "node:test";

import { mapPeriodLabel, mapStatsPath } from "./maps.ts";

test("map stats paths", () => {
  assert.equal(mapStatsPath(null, "all", "2026-10-07"), "/map-stats?period=all");
  assert.equal(mapStatsPath("bermuda", "week", "2026-10-07"), "/map-stats?period=week&map=bermuda&date=2026-10-07");
  assert.equal(mapStatsPath("solara", "month", null), "/map-stats?period=month&map=solara");
});

test("map period label", () => {
  assert.equal(mapPeriodLabel({ period: "all", start: null, end: null }), "All time");
  assert.equal(mapPeriodLabel({ period: "month", start: "2026-10-01", end: "2026-10-31" }), "October 2026");
});
