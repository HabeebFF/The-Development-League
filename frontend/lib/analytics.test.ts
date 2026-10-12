import assert from "node:assert/strict";
import { test } from "node:test";

import { compact, dayLabel, friendly, hitFor, hourLabel, share } from "./analytics.ts";

test("the tracker sends the referrer only on the first page", () => {
  assert.deepEqual(hitFor("/standings", "", "https://t.co/x", true), { path: "/standings", referrer: "https://t.co/x" });
  assert.deepEqual(hitFor("/teams", "", "https://t.co/x", false), { path: "/teams" });
  assert.deepEqual(hitFor("/", "?ref=wa", "", true), { path: "/", ref: "wa" });
  assert.deepEqual(hitFor("/", "?utm_source=discord", "", false), { path: "/", ref: "discord" });
});

test("numbers, days and hours read naturally", () => {
  assert.equal(compact(950), "950");
  assert.equal(compact(1234), "1,234");
  assert.equal(compact(12500), "12.5k");
  assert.equal(compact(20000), "20k");
  assert.equal(compact(250000), "250k");
  assert.equal(dayLabel("2026-10-12"), "Mon 12 Oct");
  assert.deepEqual([0, 9, 12, 20].map(hourLabel), ["12am", "9am", "12pm", "8pm"]);
  assert.equal(friendly("desktop"), "Computer");
  assert.equal(friendly("Chrome"), "Chrome");
});

test("bar widths", () => {
  assert.equal(share(0, 10), 0);
  assert.equal(share(5, 10), 50);
  assert.equal(share(1, 1000), 2);
  assert.equal(share(3, 0), 0);
});
