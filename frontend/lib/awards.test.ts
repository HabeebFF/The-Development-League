import assert from "node:assert/strict";
import { test } from "node:test";

import { periodLabel, unit } from "./awards.ts";

test("periods read as a date range or a month", () => {
  assert.equal(periodLabel({ period: "week", start: "2026-10-05", end: "2026-10-11" }), "5 – 11 Oct");
  assert.equal(periodLabel({ period: "week", start: "2026-09-28", end: "2026-10-04" }), "28 Sept – 4 Oct");
  assert.equal(periodLabel({ period: "month", start: "2026-10-01", end: "2026-10-31" }), "October 2026");
});

test("units match the award", () => {
  assert.equal(unit("player", 1), "kill");
  assert.equal(unit("sniper", 3), "sniper kills");
  assert.equal(unit("grenader", 2), "explosive kills");
});
