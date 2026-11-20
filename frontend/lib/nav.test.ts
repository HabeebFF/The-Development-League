import assert from "node:assert/strict";
import { test } from "node:test";

import { SECTIONS, activeLink, meLinks, sectionFor } from "./nav.ts";

const key = (path: string) => sectionFor(path)?.key ?? null;
const section = (k: string) => SECTIONS.find((s) => s.key === k)!;

test("every league page lights up the League section", () => {
  for (const p of ["/standings", "/results", "/results/12", "/teams", "/teams/slf", "/tournaments/cup", "/protection-points", "/matches/4", "/matches/4/replay"]) {
    assert.equal(key(p), "league", p);
  }
});

test("player pages go to Players, prediction and shop pages to Predict", () => {
  for (const p of ["/players", "/kills", "/ratings", "/cards", "/cards/7", "/awards", "/maps"]) assert.equal(key(p), "players", p);
  for (const p of ["/predict", "/predict/markets/3", "/predict/mine", "/predict/wallet", "/predict/leaderboard", "/shop", "/player-shop", "/player-shop/perks"]) {
    assert.equal(key(p), "predict", p);
  }
});

test("home, account, team and staff pages sit outside the sections", () => {
  for (const p of ["/", "/account", "/team", "/team/members", "/staff", "/staff/upload", "/create-team", "/privacy"]) assert.equal(key(p), null, p);
});

test("no page appears in two sections", () => {
  const all = SECTIONS.flatMap((s) => s.links.map((l) => l.href));
  assert.equal(new Set(all).size, all.length);
});

test("the most specific tab wins, and a market counts as Matches", () => {
  const predict = section("predict");
  assert.equal(activeLink("/predict/mine", predict), "/predict/mine");
  assert.equal(activeLink("/predict", predict), "/predict");
  assert.equal(activeLink("/predict/markets/9", predict), "/predict");
  assert.equal(activeLink("/players", section("players")), null);
});

const base = { staff_role: null, memberships: [], player: null };

test("Me: visitors get nothing, fans get account and Start a team", () => {
  assert.deepEqual(meLinks(null), []);
  assert.deepEqual(
    meLinks(base).map((l) => l.href),
    ["/account", "/create-team"],
  );
});

test("Me: a team player sees My team and the player shop; staff see Staff", () => {
  assert.deepEqual(
    meLinks({ ...base, memberships: [{}], player: { game_uid: "1" } }).map((l) => l.href),
    ["/account", "/team", "/player-shop"],
  );
  assert.deepEqual(
    meLinks({ ...base, staff_role: "STAFF" }).map((l) => l.href),
    ["/account", "/staff"],
  );
});
