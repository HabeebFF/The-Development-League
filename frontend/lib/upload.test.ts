import assert from "node:assert/strict";
import { test } from "node:test";

import {
  chunk,
  classify,
  dayHint,
  daysIn,
  inPlayOrder,
  numberFor,
  pickMatchFiles,
  roomName,
  sameDayName,
  sessionsOf,
  isLeagueRoom,
  retryDelay,
  speed,
  timeLeft,
  type PreviewMatch,
} from "./upload.ts";

test("classifies observer files and debugger logs like the server", () => {
  assert.deepEqual(
    classify("MatchResult_2103980121133858816_2026-09-27-00-05-01.log"),
    {
      kind: "MATCH_RESULT",
      matchId: "2103980121133858816",
      day: "2026-09-27",
    },
  );
  assert.equal(
    classify("Free Fire_64_Data/ReplayInfo_21_2026-09-28-22-50-50.bin")?.kind,
    "REPLAY_BIN",
  );
  assert.equal(
    classify("C:\\game\\ReplayInfo_21_2026-09-28-22-50-50.json")?.kind,
    "REPLAY_JSON",
  );
  assert.deepEqual(classify("debugger-2026-09-26T19-41-10.log"), {
    kind: "DEBUGGER",
    matchId: null,
    day: "2026-09-26",
  });
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
    [
      "MatchResult_2_2026-09-30-20-00-00.log",
      "debugger-2026-09-30T19-00-00.log",
    ],
  );
  assert.deepEqual(daysIn(files), ["2026-09-30", "2026-09-29"]);
});

test("chunks by size and gives a big file its own request", () => {
  const f = (size: number) => ({ size });
  assert.deepEqual(
    chunk([f(10), f(20), f(15), f(100), f(5)], 40).map((c) =>
      c.map((x) => x.size),
    ),
    [[10, 20], [15], [100], [5]],
  );
  assert.deepEqual(chunk([], 40), []);
});

test("orders matches by start time and finds the day in room names", () => {
  const m = (id: string, started: string | null, hint: number | null) =>
    ({
      game_match_id: id,
      started_at: started,
      match_day_hint: hint,
    }) as PreviewMatch;
  const order = inPlayOrder([
    m("3", null, 12),
    m("2", "2026-09-30T20:30:00", 12),
    m("1", "2026-09-30T20:00:00", 11),
  ]);
  assert.deepEqual(
    order.map((x) => x.game_match_id),
    ["1", "2", "3"],
  );
  assert.equal(dayHint(order), 12);
  assert.equal(dayHint([m("1", null, null)]), null);
});

test("the match day comes from the room name", () => {
  const r = (room_name: string) => ({ room_name });
  assert.equal(
    roomName([r("TDL  DAY 12 "), r("TDL DAY 12"), r("scrim")]),
    "TDL DAY 12",
  );
  assert.equal(roomName([r(""), r("  ")]), null);
  assert.ok(sameDayName("TDL Day 12", "tdl  DAY 12"));
  assert.ok(!sameDayName("TDL Day 12", "TDL Day 11"));
  assert.ok(!sameDayName("", ""));
});

test("matches are numbered for the chosen day", () => {
  const m = (
    id: string,
    existing: { match_day: number; number: number } | null,
  ) =>
    ({
      game_match_id: id,
      existing_match: existing && { id: 1, status: "PUBLISHED", ...existing },
    }) as PreviewMatch;
  // Day 12 matches filed under day 1 as 11 and 12: moving them to day 2 numbers them 1, 2.
  const order = [
    m("a", { match_day: 1, number: 11 }),
    m("b", { match_day: 1, number: 12 }),
    m("c", null),
  ];
  assert.deepEqual(numberFor(order, 2), { a: 1, b: 2, c: 3 });
  assert.deepEqual(numberFor(order, 1), { a: 11, b: 12, c: 13 });
  assert.deepEqual(numberFor(order, null), { a: 1, b: 2, c: 3 });
});

test("an 8pm and a 10pm session become two match days", () => {
  const at = (h: number, m: number) => new Date(2026, 9, 1, h, m).toISOString();
  const m = (id: string, started: string) =>
    ({
      game_match_id: id,
      started_at: started,
      room_name: "TDL DAY 12",
    }) as PreviewMatch;
  const order = [
    m("1", at(20, 2)),
    m("2", at(20, 26)),
    m("3", at(20, 50)),
    m("4", at(21, 14)),
    m("5", at(21, 38)),
    m("6", at(22, 1)),
    m("7", at(22, 25)),
  ];
  const s = sessionsOf(order);
  assert.deepEqual(
    s.map((x) => [x.name, x.matches.map((y) => y.game_match_id)]),
    [
      ["TDL DAY 12 8PM", ["1", "2", "3", "4", "5"]],
      ["TDL DAY 12 10PM", ["6", "7"]],
    ],
  );
  // A long break also starts a new session.
  assert.equal(
    sessionsOf([m("1", at(18, 0)), m("2", at(18, 24)), m("3", at(19, 30))])
      .length,
    2,
  );
  // One session keeps the plain room name.
  assert.deepEqual(
    sessionsOf(order.slice(0, 3)).map((x) => x.name),
    ["TDL DAY 12"],
  );
});

test("other organisers' scrims are their own sessions, after TDL's", () => {
  const at = (h: number, m: number) => new Date(2026, 9, 2, h, m).toISOString();
  const m = (id: string, started: string, room: string) =>
    ({
      game_match_id: id,
      started_at: started,
      room_name: room,
    }) as PreviewMatch;
  const order = [
    m("h1", at(14, 19), "HYDRA SCRIMS"),
    m("h2", at(14, 42), "HYDRA  SCRIMS"),
    m("h3", at(15, 6), "HYDRA SCRIMS"),
    m("t1", at(20, 2), "TDL DAY 14"),
    m("t2", at(20, 26), "TDL DAY 14"),
    m("t3", at(22, 1), "TDL DAY 14"),
  ];
  const s = sessionsOf(order);
  assert.deepEqual(
    s.map((x) => [x.name, x.league, x.matches.map((y) => y.game_match_id)]),
    [
      ["TDL DAY 14 8PM", true, ["t1", "t2"]],
      ["TDL DAY 14 10PM", true, ["t3"]],
      ["HYDRA SCRIMS", false, ["h1", "h2", "h3"]],
    ],
  );
  // Rooms that differ only by spacing or case are the same room.
  assert.ok(
    isLeagueRoom("tdl  day 3") &&
      isLeagueRoom("") &&
      !isLeagueRoom("HYDRA SCRIMS"),
  );
});

test("upload progress: time left, retry waits and speed", () => {
  assert.equal(timeLeft(5), "a few seconds left");
  assert.equal(timeLeft(42), "about 50 s left");
  assert.equal(timeLeft(200), "about 3 min left");
  assert.equal(timeLeft(Infinity), "working out time left");
  assert.deepEqual(
    [1, 2, 3, 4, 9].map(retryDelay),
    [2000, 5000, 10000, 20000, 20000],
  );
  assert.equal(speed([[0, 0]]), null);
  // Only the last 15 s count: 10 MB in the last 10 s is 1 MB/s.
  assert.equal(
    speed([
      [0, 0],
      [20000, 0],
      [30000, 10_000_000],
    ]),
    1_000_000,
  );
});
