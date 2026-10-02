import assert from "node:assert/strict";
import { test } from "node:test";

import { currentSeason, dayName, latestPlayed, mapName, ordinal, plural } from "./league.ts";

const season = (id: number, is_active: boolean) => ({ id, name: `S${id}`, slug: `s${id}`, starts_on: null, ends_on: null, is_active });

test("the active season wins, else the newest", () => {
  assert.equal(currentSeason([season(2, false), season(1, true)])?.id, 1);
  assert.equal(currentSeason([season(2, false), season(1, false)])?.id, 2);
  assert.equal(currentSeason([]), null);
});

test("latest played day skips days with no played match", () => {
  const day = (id: number, played: boolean[], date: string | null = null) => ({ id, number: id, date, matches: played.map((p) => ({ played: p })) });
  const days = [day(1, [true]), day(2, [true, false]), day(3, [false])] as never[];
  assert.equal((latestPlayed(days) as { id: number } | null)?.id, 2);
  // A dated day beats an undated one, whatever the day number.
  const dated = [day(11, [true], "2026-09-28"), day(10, [true])] as never[];
  assert.equal((latestPlayed(dated) as { id: number } | null)?.id, 11);
  assert.equal(latestPlayed([]), null);
});

test("ordinals, day names and map names", () => {
  assert.deepEqual([1, 2, 3, 4, 11, 12, 13, 21, 22, 112].map(ordinal), ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "112th"]);
  assert.equal(dayName({ title: "", number: 12 }), "Day 12");
  assert.equal(dayName({ title: "TDL DAY 12", number: 12 }), "TDL DAY 12");
  assert.equal(mapName("bermuda"), "Bermuda");
  assert.equal(mapName(null), "Unknown map");
  assert.equal(plural(1, "kill"), "1 kill");
  assert.equal(plural(0, "kill"), "0 kills");
});
