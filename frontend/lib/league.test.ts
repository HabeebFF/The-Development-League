import assert from "node:assert/strict";
import { test } from "node:test";

import { currentSeason, dayName, latestPlayed, mapName, ordinal, overallMovement, plural, type StandingRow } from "./league.ts";

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

const row = (id: number, rank: number, total_points: number, matches_played = 5, booyahs = 0, kills = 0): StandingRow => ({
  rank,
  team: { id, name: `T${id}`, tag: `T${id}`, slug: `t${id}`, logo: null, primary_color: "" },
  matches_played,
  booyahs,
  kills,
  placement_points: 0,
  kill_points: kills,
  total_points,
  avg_placement: null,
  last_match_points: null,
  form: [],
});

test("overallMovement compares the table with and without the latest day", () => {
  // Before the latest day: A 100, B 90, C 80. Latest day: C +40, A +5, B +5.
  const overall = [row(3, 1, 120, 10), row(1, 2, 105, 10), row(2, 3, 95, 10)];
  const day = [row(3, 1, 40), row(1, 2, 5), row(2, 3, 5)];
  const m = overallMovement(overall, day);
  assert.equal(m.get(3), 2); // 3rd -> 1st
  assert.equal(m.get(1), -1); // 1st -> 2nd
  assert.equal(m.get(2), -1); // 2nd -> 3rd
});

test("overallMovement: no change is 0, a team new on the latest day is null", () => {
  const overall = [row(1, 1, 50, 10), row(2, 2, 40, 10), row(9, 3, 10, 5)];
  const day = [row(1, 1, 10), row(2, 2, 8), row(9, 3, 10)];
  const m = overallMovement(overall, day);
  assert.equal(m.get(1), 0);
  assert.equal(m.get(2), 0);
  assert.equal(m.get(9), null);
});
