import assert from "node:assert/strict";
import { test } from "node:test";

import { homeFor, isOpenPath } from "./home.ts";

test("staff land in Staff and team members in their team area", () => {
  assert.equal(homeFor({ staff_role: "STAFF" }), "/staff");
  assert.equal(homeFor({ staff_role: "SUPER_ADMIN" }), "/staff");
  assert.equal(homeFor({ staff_role: null }), "/team");
});

test("only sign-in and invite pages are open without an account", () => {
  for (const path of ["/auth/login", "/auth/reset", "/invite/abc123"]) assert.ok(isOpenPath(path), path);
  for (const path of ["/", "/standings", "/teams/x", "/staff", "/team", "/authors", "/invites"])
    assert.ok(!isOpenPath(path), path);
});
