import assert from "node:assert/strict";
import { test } from "node:test";

import { dateSpan, dc, naira, tournamentFor } from "./tournaments.ts";

test("money and coins", () => {
  assert.equal(naira(100000), "₦100,000");
  assert.equal(dc(1000000), "1,000,000 DC");
});

test("a room name finds its tournament by keyword", () => {
  const list = [
    { keyword: "CUP", status: "live", slug: "cup" },
    { keyword: "", status: "live", slug: "none" },
    { keyword: "OLD", status: "finished", slug: "old" },
  ];
  assert.equal(tournamentFor("TDL Cup Day 1 10PM", list)?.slug, "cup");
  assert.equal(tournamentFor("TDL DAY 30 10PM", list), null);
  assert.equal(tournamentFor("OLD CUP", [list[2]]), null); // finished ones don't take uploads
});

test("date spans", () => {
  assert.equal(dateSpan("2026-11-16", "2026-11-17"), "16 to 17 Nov");
  assert.equal(dateSpan("2026-11-30", "2026-12-01"), "30 Nov to 1 Dec");
  assert.equal(dateSpan("2026-11-16", null), "16 Nov");
  assert.equal(dateSpan(null, null), "");
});
