import assert from "node:assert/strict";
import { describe, it, test } from "node:test";

import { dataText, headToHeadText, matchesReview, parseData, sourceLine } from "./coach.ts";

describe("knowledge base data box", () => {
  it("round-trips named values", () => {
    const data = { scan_radius_m: 65, note: "player UAV" };
    assert.deepEqual(parseData(dataText(data)), data);
  });

  it("treats an empty box as no values, and rejects anything but an object", () => {
    assert.equal(dataText({}), "");
    assert.deepEqual(parseData("  "), {});
    assert.equal(parseData("[1, 2]"), null);
    assert.equal(parseData("{oops"), null);
    assert.equal(parseData("12"), null);
  });
});

import { factsByTopic, type Fact } from "./coach.ts";

describe("report facts", () => {
  const f = (id: string, topic: string, map: string | null = null): Fact => ({
    id,
    topic,
    text: id,
    value: 0,
    n: 3,
    of: 3,
    matches: [1],
    map,
    data: {},
  });

  it("groups facts by topic in reading order, overall before each map", () => {
    const groups = factsByTopic([
      f("kalahari:drops.usual", "drops", "kalahari"),
      f("fights.record", "fights"),
      f("bermuda:fights.record", "fights", "bermuda"),
      f("results.placement", "results"),
    ]);
    assert.deepEqual(
      groups.map((g) => [g.key, g.facts.map((x) => x.id)]),
      [
        ["results", ["results.placement"]],
        ["fights", ["fights.record", "bermuda:fights.record"]],
        ["drops", ["kalahari:drops.usual"]],
      ],
    );
  });
});

test("head-to-head line covers never met, met without fighting, and a record", () => {
  const none = { met: [], fights: 0, won: 0, lost: 0, matches: [] };
  assert.equal(headToHeadText(none, "Cliq"), "You haven't played in the same match as Cliq yet.");
  assert.equal(headToHeadText({ ...none, met: [3] }, "Cliq"), "You've been in 1 match with Cliq but haven't fought them.");
  assert.equal(
    headToHeadText({ met: [1, 2], fights: 3, won: 1, lost: 2, matches: [1, 2] }, "Cliq"),
    "Against Cliq: won 1, lost 2 of 3 fights over 2 matches.",
  );
});

describe("knowledge review", () => {
  const e = (status: "DRAFT" | "APPROVED" | "REJECTED", body = "x", weak_sources = false) => ({ status, body, weak_sources });

  it("filters by review state", () => {
    assert.equal(matchesReview(e("DRAFT"), "DRAFT"), true);
    assert.equal(matchesReview(e("APPROVED"), "DRAFT"), false);
    assert.equal(matchesReview(e("APPROVED", ""), "WRITE"), true);
    assert.equal(matchesReview(e("DRAFT", "x", true), "WEAK"), true);
    assert.equal(matchesReview(e("REJECTED", "x", true), "WEAK"), false);
    assert.equal(matchesReview(e("REJECTED"), "ALL"), true);
  });

  it("describes a source by publisher and date", () => {
    assert.equal(sourceLine({ url: "https://ff.garena.com/en/article/1712/", publisher: "Garena", published: "2026-09-10" }), "Garena, 2026-09-10");
    assert.equal(sourceLine({ url: "https://www.vandal.net/x", accessed: "2026-10-03" }), "vandal.net, no date, read 2026-10-03");
  });
});
