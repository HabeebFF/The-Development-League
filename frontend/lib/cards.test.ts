import assert from "node:assert/strict";
import { test } from "node:test";

import { cardFileName, changeText, roleShort, totwText, weekLabel } from "./cards.ts";

test("changes read as arrows, nothing when flat", () => {
  assert.equal(changeText(3), "▲ 3");
  assert.equal(changeText(-2), "▼ 2");
  assert.equal(changeText(0), "");
  assert.equal(changeText(null), "");
});

test("weeks, roles and awards read plainly", () => {
  assert.equal(weekLabel("2026-10-05"), "5 – 11 Oct");
  assert.equal(weekLabel("2026-09-28"), "28 Sept – 4 Oct");
  assert.equal(roleShort("GRENADER"), "NDR");
  assert.equal(totwText(["player", "sniper"]), "Team of the Week: Top player, Top sniper");
  assert.equal(totwText([]), "");
});

test("saved cards get a tidy file name", () => {
  assert.equal(cardFileName({ name: "ÁCE • Killer!", week: "2026-10-05" }), "tdl-card-ace-killer-2026-10-05.png");
  assert.equal(cardFileName({ name: "★★", week: "2026-10-05" }), "tdl-card-player-2026-10-05.png");
});
