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

test("clicks become actions", async () => {
  const { describeClick } = await import("./analytics.ts");
  const origin = "https://tdl.test";
  assert.deepEqual(describeClick({ tag: "button", label: "  Play\n" }), { name: 'Pressed "Play"' });
  assert.deepEqual(describeClick({ tag: "button", label: "" }), { name: "Pressed a button" });
  assert.deepEqual(describeClick({ tag: "a", label: "OUTPOST-33", href: "/teams/outpost-33", origin }), {
    name: 'Clicked "OUTPOST-33"',
    detail: "/teams/outpost-33",
  });
  assert.deepEqual(describeClick({ tag: "a", label: "VOD", href: "https://youtube.com/watch?v=1", origin }), {
    name: "Opened a link to another site",
    detail: "youtube.com/watch",
  });
  assert.equal(describeClick({ tag: "a", label: "Mail", href: "mailto:x@y.z", origin }), null);
  assert.deepEqual(describeClick({ tag: "button", label: "x", track: "Followed a team", trackDetail: "Vortex" }), {
    name: "Followed a team",
    detail: "Vortex",
  });
});

test("changes become actions, typing never does", async () => {
  const { describeChange, duration } = await import("./analytics.ts");
  assert.deepEqual(describeChange({ tag: "select", label: "Team", value: "Vortex" }), { name: 'Picked "Vortex"', detail: "Team" });
  assert.deepEqual(describeChange({ tag: "input", type: "checkbox", label: "Show labels", checked: false }), { name: 'Unticked "Show labels"' });
  assert.deepEqual(describeChange({ tag: "input", type: "range", label: "Time", value: "312" }), { name: 'Moved "Time"', detail: "312" });
  assert.deepEqual(describeChange({ tag: "input", type: "search", label: "", value: "habeeb" }), { name: "Searched", detail: "habeeb" });
  assert.equal(describeChange({ tag: "input", type: "password", label: "Password", value: "secret" }), null);
  assert.equal(describeChange({ tag: "input", type: "text", label: "Name", value: "x" }), null);
  assert.deepEqual(describeChange({ tag: "input", type: "file", label: "Logs", files: 3 }), { name: "Chose 3 files", detail: "Logs" });
  assert.deepEqual([duration(null), duration(45), duration(80), duration(7500)], ["–", "45s", "1m 20s", "2h 05m"]);
});

test("league time helpers", async () => {
  const { clock, deviceLine, leagueToday, shiftDay } = await import("./analytics.ts");
  assert.equal(clock("2026-10-15T19:14:00Z"), "20:14");
  assert.equal(leagueToday(new Date("2026-10-15T23:30:00Z")), "2026-10-16");
  assert.equal(shiftDay("2026-10-01", -1), "2026-09-30");
  assert.equal(shiftDay("2026-12-31", 1), "2027-01-01");
  assert.equal(deviceLine({ device: "phone", os: "Android", browser: "Chrome" }), "Android phone, Chrome");
  assert.equal(deviceLine({ device: "desktop", os: "Other", browser: "Firefox" }), "computer, Firefox");
});
