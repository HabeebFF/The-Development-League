import assert from "node:assert/strict";
import { test } from "node:test";

import { partText, pointsText, ratingsPath, ratingText } from "./ratings.ts";

test("paths ask for the latest day until one is picked", () => {
  assert.equal(ratingsPath(null), "/ratings");
  assert.equal(ratingsPath("2026-10-12"), "/ratings?date=2026-10-12");
  assert.equal(ratingsPath("2026-10-12", 7), "/ratings?date=2026-10-12&session=7");
});

test("ratings always show one decimal", () => {
  assert.equal(ratingText(7), "7.0");
  assert.equal(ratingText(8.4), "8.4");
});

test("parts read as plain sentences", () => {
  assert.equal(pointsText(0.54), "+0.54");
  assert.equal(pointsText(-0.2), "−0.20");
  assert.equal(partText({ key: "placement", label: "Team placement", count: 1, points: 1 }), "Booyah");
  assert.equal(partText({ key: "placement", label: "Team placement", count: 12, points: -0.4 }), "Team 12th");
  assert.equal(partText({ key: "placement", label: "Team placement", count: 3, points: 0.5 }), "Team 3rd");
  assert.equal(partText({ key: "survival", label: "Time alive", count: 0.84, points: 0.41 }), "Alive 84% of the match");
  assert.equal(partText({ key: "kills", label: "Kills", count: 3, points: 0.54 }), "Kills: 3");
});
