import assert from "node:assert/strict";
import { test } from "node:test";

import {
  asSpecial,
  cardFileName,
  cardFooter,
  changeText,
  countdown,
  nextRelease,
  monthLabel,
  roleShort,
  runLabel,
  totwText,
  weekLabel,
  type PlayerCard,
} from "./cards.ts";

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
  assert.equal(
    totwText(["player", "sniper"]),
    "Team of the Week: Top player, Top sniper",
  );
  assert.equal(totwText([]), "");
});

test("saved cards get a tidy file name", () => {
  assert.equal(
    cardFileName({ name: "ÁCE • Killer!", week: "2026-10-05" }),
    "tdl-card-ace-killer-2026-10-05.png",
  );
  assert.equal(
    cardFileName({ name: "★★", week: "2026-10-05" }),
    "tdl-card-player-2026-10-05.png",
  );
});

test("months read in full", () => {
  assert.equal(monthLabel("2026-10-01"), "October 2026");
});

test("next cards come out at midnight in Lagos, Friday 23:00 UTC", () => {
  const friday = new Date("2026-10-09T18:00:00Z");
  assert.equal(nextRelease(friday).toISOString(), "2026-10-09T23:00:00.000Z");
  assert.equal(
    nextRelease(new Date("2026-10-09T22:59:59Z")).toISOString(),
    "2026-10-09T23:00:00.000Z",
  );
  assert.equal(
    nextRelease(new Date("2026-10-09T23:00:00Z")).toISOString(),
    "2026-10-16T23:00:00.000Z",
  );
  assert.deepEqual(countdown(friday, nextRelease(friday)), {
    d: 0,
    h: 5,
    m: 0,
    s: 0,
  });
});

test("an Icon run reads from its first Saturday to its last Friday", () => {
  assert.equal(runLabel("2026-10-03", "2026-10-31"), "3 Oct to 6 Nov");
});

test("card footers name the special cards", () => {
  const base = {
    tier: "gold",
    stale: false,
    totw: [],
  } as unknown as PlayerCard;
  assert.equal(
    cardFooter({ ...base, tier: "rising", rise: 12 }),
    "Rising star · +12",
  );
  assert.equal(cardFooter({ ...base, tier: "icon" }), "Icon");
  assert.equal(cardFooter(base), "TDL");
});

test("special versions show only when opened from their own tab", () => {
  const plain = {
    tier: "gold",
    totw: ["rusher"],
    special: "rising_star",
    rise: 12,
  } as unknown as PlayerCard;
  assert.equal(asSpecial(plain).tier, "gold");
  assert.equal(asSpecial(plain, "totw").tier, "totw");
  assert.equal(asSpecial(plain, "rising").tier, "rising");
  assert.equal(asSpecial(plain, "icon").tier, "gold"); // not an Icon
  const month = asSpecial(plain, "totm", "sniper");
  assert.equal(month.tier, "totm");
  assert.equal(month.totm, "sniper");
  assert.equal(asSpecial(plain, "totm", "nonsense").tier, "gold");
});
