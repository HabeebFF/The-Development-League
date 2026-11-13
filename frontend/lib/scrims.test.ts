import assert from "node:assert/strict";
import { test } from "node:test";

import { action, clock, lagosToday, myStatus, nightName, places, stageText, weekdayList, type ScrimSession } from "./scrims.ts";

const session = (over: Partial<ScrimSession> = {}): ScrimSession => ({
  date: "2026-11-16",
  session: "8PM",
  stage: "open",
  opens_at: "2026-11-16T12:01:00+01:00",
  closes_at: "2026-11-16T18:00:00+01:00",
  starts_at: "2026-11-16T20:00:00+01:00",
  max_teams: 12,
  playing: [],
  waitlist: [],
  mine: null,
  ...over,
});

test("times read in Lagos time", () => {
  assert.equal(clock("2026-11-16T12:01:00+01:00"), "12:01pm");
  assert.equal(clock("2026-11-16T17:00:00Z"), "6:00pm");
  assert.equal(lagosToday(new Date("2026-11-16T23:30:00Z")), "2026-11-17");
});

test("night names", () => {
  const now = new Date("2026-11-16T10:00:00Z");
  assert.equal(nightName("2026-11-16", now), "Tonight");
  assert.equal(nightName("2026-11-19", now), "Thursday 19 Nov");
});

test("stage lines", () => {
  assert.equal(stageText(session({ stage: "soon" })), "Sign-up opens 12:01pm");
  assert.equal(stageText(session()), "Sign-up open until 6:00pm");
  assert.equal(stageText(session({ stage: "closed" })), "Sign-up closed · starts 8:00pm");
});

test("places left", () => {
  const team = { id: 1, name: "A", tag: "", slug: "a", logo: null, primary_color: "" };
  assert.deepEqual(places(session({ playing: Array(11).fill({ team, by_staff: false }) })), { taken: "11/12", left: 1 });
});

test("a team's status and button", () => {
  assert.equal(myStatus(session({ mine: "REGISTERED" })), "You're in");
  assert.equal(myStatus(session({ mine: "WAITLIST", waitlist_place: 2 })), "Waitlist, #2");
  assert.equal(myStatus(session({ mine: "WAITLIST", stage: "closed" })), "Waitlisted: not playing");
  assert.equal(action(session(), true, false), "register");
  assert.equal(action(session(), true, true), null); // suspended
  assert.equal(action(session(), false, false), null); // players can't
  assert.equal(action(session({ mine: "WAITLIST" }), true, false), "withdraw");
  assert.equal(action(session({ stage: "closed", mine: "REGISTERED" }), true, false), null);
});

test("weekday list", () => {
  assert.equal(weekdayList([4, 0, 1, 3]), "Mon, Tue, Thu, Fri");
  assert.equal(weekdayList([]), "None");
});
