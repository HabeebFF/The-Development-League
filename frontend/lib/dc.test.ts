import assert from "node:assert/strict";
import { test } from "node:test";

import { breakdown, dc } from "./dc.ts";

test("lists what a match paid for", () => {
  assert.equal(breakdown({ kills: 3, booyah: true, mvp: true }), "3 kills · Booyah · MVP");
  assert.equal(breakdown({ kills: 1, booyah: false, mvp: false }), "1 kill");
  assert.equal(breakdown({ kills: 0, booyah: false, mvp: false }), "played");
});

test("formats DC", () => {
  assert.equal(dc(12400), "12,400 DC");
});
