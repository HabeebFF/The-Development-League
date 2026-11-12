import assert from "node:assert/strict";
import { test } from "node:test";

import type { MatchDay } from "./api.ts";
import { groupResults, resultMaps, resultWeeks } from "./results.ts";

const m = (id: number, number: number, map: string | null) => ({ id, number, map, scheduled_at: null, started_at: null, played: true, booyah: null, vod_url: null });
const day = (id: number, date: string, maps: (string | null)[]): MatchDay => ({ id, number: id, title: `Day ${id}`, date, stage: "", group: null, matches: maps.map((mp, i) => m(id * 10 + i, maps.length - i, mp)) });
const days = [day(3, "2026-11-09", ["bermuda", "kalahari"]), day(2, "2026-11-09", ["purgatory"]), day(1, "2026-11-01", ["bermuda", "alpine"])];

test("groups sessions by date and orders matches", () => {
  const g = groupResults(days, { startsOn: "2026-11-01" });
  assert.deepEqual(g.map((d) => [d.date, d.week, d.days.map((x) => x.day.id)]), [["2026-11-09", 2, [3, 2]], ["2026-11-01", 1, [1]]]);
  assert.deepEqual(g[0].days[0].matches.map((x) => x.number), [1, 2]);
});

test("filters by week and map", () => {
  assert.deepEqual(groupResults(days, { startsOn: "2026-11-01", week: 1 }).map((d) => d.date), ["2026-11-01"]);
  const b = groupResults(days, { map: "bermuda" });
  assert.deepEqual(b.map((d) => d.days.map((x) => x.day.id)), [[3], [1]]);
  assert.ok(b.every((d) => d.days.every((x) => x.matches.every((mm) => mm.map === "bermuda"))));
});

test("lists weeks newest first and maps in league order", () => {
  assert.deepEqual(resultWeeks(days, "2026-11-01"), [2, 1]);
  assert.deepEqual(resultWeeks(days, null), []);
  assert.deepEqual(resultMaps(days), ["bermuda", "purgatory", "kalahari", "alpine"]);
});
