import assert from "node:assert/strict";
import { test } from "node:test";

import { countUpValue, easeOut } from "./countup.ts";

test("easeOut starts at 0, ends at 1 and clamps", () => {
  assert.equal(easeOut(0), 0);
  assert.equal(easeOut(1), 1);
  assert.equal(easeOut(-1), 0);
  assert.equal(easeOut(2), 1);
  assert.ok(easeOut(0.5) > 0.5, "ease-out is past halfway at the midpoint");
});

test("countUpValue lands exactly on the final number", () => {
  assert.equal(countUpValue(173, 1), "173");
  assert.equal(countUpValue(6.6, 1, 1), "6.6");
  assert.equal(countUpValue(173, 0), "0");
  assert.equal(countUpValue(41, 5), "41");
});

test("countUpValue rounds to the asked decimals on the way", () => {
  assert.match(countUpValue(9.25, 0.5, 2), /^\d\.\d\d$/);
  assert.match(countUpValue(4386, 0.3), /^\d+$/);
});
