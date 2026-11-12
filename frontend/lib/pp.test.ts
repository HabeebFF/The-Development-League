import assert from "node:assert/strict";
import { test } from "node:test";

import { groups, outcome, periodRange, ppLedger, rewardText, ruleText, signed, type PPRow, type PPTeam } from "./pp.ts";

const row = (pp: number) => ({ pp }) as PPRow;

test("signed numbers", () => {
  assert.equal(signed(2), "+2");
  assert.equal(signed(0), "0");
  assert.equal(signed(-1), "-1");
});

test("groups skip empty ones", () => {
  assert.deepEqual(
    groups([row(4), row(0), row(0)]).map((g) => [g.key, g.rows.length]),
    [
      ["up", 1],
      ["zero", 2],
    ],
  );
});

test("rules and rewards read plainly", () => {
  assert.equal(
    ruleText({ rule: "ZONE_ALIVE", params: { zone: 5, min_matches: 4 } }),
    "Every player alive when zone 5 appears, in at least 4 matches",
  );
  assert.equal(ruleText({ rule: "DAY_POINTS", params: { op: "lt", value: 45 } }), "Less than 45 points for the day");
  assert.equal(rewardText({ rule: "ZONE_ALIVE", params: {}, pp_done: 1, pp_not_done: -1 }), "+1 PP · -1 PP if not done");
  assert.equal(rewardText({ rule: "BOOYAH", params: {}, pp_done: 2, pp_not_done: 0 }), "+2 PP each");
});

test("period range", () => {
  assert.equal(periodRange({ starts_on: "2026-10-12", ends_on: "2026-10-25" }), "12 – 25 Oct");
  assert.equal(periodRange({ starts_on: "2026-10-26", ends_on: "2026-11-08" }), "26 Oct – 8 Nov");
});

test("penalty tasks read as penalty or safe", () => {
  assert.equal(outcome({ pp_done: -1 }, true), "Penalty");
  assert.equal(outcome({ pp_done: -1 }, false), "Safe");
  assert.equal(outcome({ pp_done: 1 }, false), "Not done");
  assert.equal(outcome({ pp_done: 1 }, null), "Waiting for staff");
});

test("ledger starts with the starting PP and keeps a running total by date", () => {
  const task = (id: number, date: string, pp: number) => ({ id, date, title: `T${id}`, rule: "MANUAL", params: {}, pp_done: 1, pp_not_done: 0, is_published: true, result: { pp } }) as unknown as PPTeam["tasks"][number];
  const lines = ppLedger({
    tasks: [task(1, "2026-11-10", 3), task(2, "2026-11-09", -2)],
    adjustments: [
      { kind: "ADJUST", date: "2026-11-09", pp: 1, reason: "late" },
      { kind: "START", date: "2026-11-12", pp: 5, reason: "" },
    ],
  });
  assert.deepEqual(lines.map((l) => [l.kind, l.pp, l.total]), [["START", 5, 5], ["task", -2, 3], ["ADJUST", 1, 4], ["task", 3, 7]]);
});
