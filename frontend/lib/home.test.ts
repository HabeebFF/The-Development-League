import assert from "node:assert/strict";
import { test } from "node:test";

import { homeFor, isOpenPath, isPublicPath, podiumOrder, seasonWeek } from "./home.ts";

test("staff land in Staff and team members in their team area", () => {
  assert.equal(homeFor({ staff_role: "STAFF" }), "/staff");
  assert.equal(homeFor({ staff_role: "SUPER_ADMIN" }), "/staff");
  assert.equal(homeFor({ staff_role: null }), "/team");
  assert.equal(homeFor({ staff_role: null, memberships: [{}] }), "/team");
  assert.equal(homeFor({ staff_role: null, memberships: [] }), "/");
});

test("only sign-in and invite pages are open without an account", () => {
  for (const path of ["/auth/login", "/auth/reset", "/invite/abc123", "/privacy"]) assert.ok(isOpenPath(path), path);
  for (const path of ["/", "/standings", "/teams/x", "/staff", "/team", "/authors", "/invites"])
    assert.ok(!isOpenPath(path), path);
});

test("league pages, replays and rotations are public while the site is open", () => {
  for (const path of ["/", "/standings", "/results/3", "/teams/x", "/matches/5", "/matches/5/replay", "/matches/5/rotations", "/awards", "/kills", "/maps", "/ratings", "/cards", "/cards/7", "/protection-points", "/predict", "/predict/markets/4", "/predict/leaderboard", "/shop"])
    assert.ok(isPublicPath(path), path);
  for (const path of ["/staff", "/staff/coach", "/team", "/team/coach", "/teamsx", "/auth/login", "/predictx", "/shopx"]) assert.ok(!isPublicPath(path), path);
});

test("seasonWeek counts the first day of the season as week 1", () => {
  assert.equal(seasonWeek("2026-09-01", "2026-09-01"), 1);
  assert.equal(seasonWeek("2026-09-01", "2026-09-07"), 1);
  assert.equal(seasonWeek("2026-09-01", "2026-09-08"), 2);
  assert.equal(seasonWeek("2026-09-01", "2026-11-09T19:00:00Z"), 10);
});

test("seasonWeek is null without dates or before the season", () => {
  assert.equal(seasonWeek(null, "2026-09-08"), null);
  assert.equal(seasonWeek("2026-09-01", null), null);
  assert.equal(seasonWeek("2026-09-10", "2026-09-01"), null);
});

test("podiumOrder puts first in the middle", () => {
  const rows = [{ rank: 1 }, { rank: 2 }, { rank: 3 }, { rank: 4 }];
  assert.deepEqual(podiumOrder(rows).map((r) => r.rank), [2, 1, 3]);
  assert.deepEqual(podiumOrder([{ rank: 1 }, { rank: 2 }]).map((r) => r.rank), [1, 2]);
});
