import assert from "node:assert/strict";
import { test } from "node:test";

import { homeFor } from "./home.ts";

test("staff land in Staff and team members in their team area", () => {
  assert.equal(homeFor({ staff_role: "STAFF" }), "/staff");
  assert.equal(homeFor({ staff_role: "SUPER_ADMIN" }), "/staff");
  assert.equal(homeFor({ staff_role: null }), "/team");
});
