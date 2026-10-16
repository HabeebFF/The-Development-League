import assert from "node:assert/strict";
import { test } from "node:test";

import { homeFor, isOpenPath, isPublicPath } from "./home.ts";

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
  for (const path of ["/", "/standings", "/results/3", "/teams/x", "/matches/5", "/matches/5/replay", "/matches/5/rotations", "/awards", "/kills", "/ratings", "/cards", "/cards/7", "/protection-points", "/predict", "/predict/markets/4", "/predict/leaderboard"])
    assert.ok(isPublicPath(path), path);
  for (const path of ["/staff", "/staff/coach", "/team", "/team/coach", "/teamsx", "/auth/login", "/predictx"]) assert.ok(!isPublicPath(path), path);
});
