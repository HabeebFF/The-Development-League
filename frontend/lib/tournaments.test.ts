import assert from "node:assert/strict";
import { test } from "node:test";

import { dateSpan, dc, entryText, naira, placesLeft, regText, tournamentFor, type Registration } from "./tournaments.ts";

test("money and coins", () => {
  assert.equal(naira(100000), "₦100,000");
  assert.equal(dc(1000000), "1,000,000 DC");
});

test("a room name finds its tournament by keyword", () => {
  const list = [
    { keyword: "CUP", status: "live", slug: "cup" },
    { keyword: "", status: "live", slug: "none" },
    { keyword: "OLD", status: "finished", slug: "old" },
    { keyword: "GONE", status: "cancelled", slug: "gone" },
  ];
  assert.equal(tournamentFor("TDL Cup Day 1 10PM", list)?.slug, "cup");
  assert.equal(tournamentFor("TDL DAY 30 10PM", list), null);
  assert.equal(tournamentFor("OLD CUP", [list[2]]), null); // finished ones don't take uploads
  assert.equal(tournamentFor("GONE CUP", [list[3]]), null); // nor cancelled ones
});

test("date spans", () => {
  assert.equal(dateSpan("2026-11-16", "2026-11-17"), "16 to 17 Nov");
  assert.equal(dateSpan("2026-11-30", "2026-12-01"), "30 Nov to 1 Dec");
  assert.equal(dateSpan("2026-11-16", null), "16 Nov");
  assert.equal(dateSpan(null, null), "");
});

const reg: Registration = {
  state: "open",
  opens_at: "2026-11-25T19:00:00Z",
  closes_at: "2026-11-28T19:00:00Z",
  fee: 10000,
  places: 24,
  taken: 24,
  waitlist: 2,
  invite_count: 8,
  qualify_count: 4,
  invited_at: null,
  advanced_at: null,
  qualifier: { id: 2, name: "Qualifier" },
  final: { id: 1, name: "Grand final" },
};

test("registration lines in Lagos time", () => {
  assert.equal(regText(reg), "Registration closes Sat 28 Nov, 8:00pm");
  assert.equal(regText({ ...reg, state: "soon" }), "Registration opens Wed 25 Nov, 8:00pm");
  assert.equal(regText({ ...reg, state: "off" }), "");
  assert.equal(placesLeft(reg), 0);
  assert.equal(placesLeft({ ...reg, taken: 20 }), 4);
});

test("a team's place", () => {
  const e = { id: 1, team: { id: 1, name: "A", slug: "a", tag: "", logo: null, primary_color: "" }, stage: 1, note: "", stage_name: "Grand final" };
  assert.equal(entryText(null), "Not registered");
  assert.equal(entryText({ ...e, via: "INVITED", status: "IN" }), "Invited to the Grand final");
  assert.equal(entryText({ ...e, via: "REGISTERED", status: "WAITLIST" }), "On the waitlist");
  assert.equal(entryText({ ...e, via: "REGISTERED", status: "IN", stage_name: "Qualifier" }), "In the Qualifier");
});
