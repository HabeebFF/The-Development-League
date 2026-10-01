import assert from "node:assert/strict";
import { test } from "node:test";

import { chunk, classify, dayHint, daysIn, inPlayOrder, pickMatchFiles, type PreviewMatch } from "./upload.ts";

test("classifies observer files and debugger logs like the server", () => {
  assert.deepEqual(classify("MatchResult_2103980121133858816_2026-09-27-00-05-01.log"), {
    kind: "MATCH_RESULT",
    matchId: "2103980121133858816",
    day: "2026-09-27",
  });
  assert.equal(classify("Free Fire_64_Data/ReplayInfo_21_2026-09-28-22-50-50.bin")?.kind, "REPLAY_BIN");
  assert.equal(classify("C:\\game\\ReplayInfo_21_2026-09-28-22-50-50.json")?.kind, "REPLAY_JSON");
  assert.deepEqual(classify("debugger-2026-09-26T19-41-10.log"), { kind: "DEBUGGER", matchId: null, day: "2026-09-26" });
  assert.equal(classify("ReplayInfo_21_2026-09-28-22-50-50.log"), null);
  assert.equal(classify("output_log.txt"), null);
});

test("keeps only match files from a folder, optionally from chosen days", () => {
  const files = [
    { name: "MatchResult_1_2026-09-29-20-00-00.log" },
    { name: "MatchResult_2_2026-09-30-20-00-00.log" },
    { name: "debugger-2026-09-30T19-00-00.log" },
    { name: "UnityPlayer.dll" },
  ];
  assert.equal(pickMatchFiles(files).length, 3);
  assert.deepEqual(
    pickMatchFiles(files, new Set(["2026-09-30"])).map((f) => f.name),
    ["MatchResult_2_2026-09-30-20-00-00.log", "debugger-2026-09-30T19-00-00.log"],
  );
  assert.deepEqual(daysIn(files), ["2026-09-30", "2026-09-29"]);
});

test("chunks by size and gives a big file its own request", () => {
  const f = (size: number) => ({ size });
  assert.deepEqual(chunk([f(10), f(20), f(15), f(100), f(5)], 40).map((c) => c.map((x) => x.size)), [
    [10, 20],
    [15],
    [100],
    [5],
  ]);
  assert.deepEqual(chunk([], 40), []);
});

test("orders matches by start time and finds the day in room names", () => {
  const m = (id: string, started: string | null, hint: number | null) =>
    ({ game_match_id: id, started_at: started, match_day_hint: hint }) as PreviewMatch;
  const order = inPlayOrder([m("3", null, 12), m("2", "2026-09-30T20:30:00", 12), m("1", "2026-09-30T20:00:00", 11)]);
  assert.deepEqual(order.map((x) => x.game_match_id), ["1", "2", "3"]);
  assert.equal(dayHint(order), 12);
  assert.equal(dayHint([m("1", null, null)]), null);
});
