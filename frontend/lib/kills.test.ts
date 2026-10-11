import assert from "node:assert/strict";
import { test } from "node:test";

import { killsLabel, killsPath } from "./kills.ts";

test("paths ask for the latest list until one is picked", () => {
  assert.equal(killsPath("session", null), "/kills?session=latest");
  assert.equal(killsPath("session", 12), "/kills?session=12");
  assert.equal(killsPath("week", null), "/kills?period=week");
  assert.equal(killsPath("month", "2026-09-30"), "/kills?period=month&date=2026-09-30");
});

test("labels name the session or the period", () => {
  const base = { matches: 5, kills: 40, players: [] };
  assert.equal(killsLabel({ ...base, scope: "session", session: { id: 3, title: "TDL DAY 12 8PM", date: null } }), "TDL DAY 12 8PM");
  assert.equal(killsLabel({ ...base, scope: "session", session: null }), "No sessions yet");
  assert.equal(killsLabel({ ...base, scope: "week", start: "2026-10-05", end: "2026-10-11" }), "5 – 11 Oct");
  assert.equal(killsLabel({ ...base, scope: "month", start: "2026-10-01", end: "2026-10-31" }), "October 2026");
});
