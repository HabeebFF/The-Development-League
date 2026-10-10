import assert from "node:assert/strict";
import { describe, it, test } from "node:test";

import {
  aiWritten,
  dataText,
  finishText,
  headToHeadText,
  matchesReview,
  parseData,
  repeatedMistakes,
  sourceLine,
  type MomentKind,
  type ReviewMatch,
  type ReviewMoment,
} from "./coach.ts";

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

test("aiWritten spots reports and plans the AI writer touched", () => {
  assert.equal(aiWritten("template"), false);
  assert.equal(aiWritten("template-1"), false);
  assert.equal(aiWritten("gemini:gemini-2.5-flash"), true);
  assert.equal(aiWritten("template-1+gemini:gemini-2.5-flash"), true);
});

describe("after-scrim review", () => {
  const moment = (kind: MomentKind, good = false): ReviewMoment => ({
    kind, good, t: 100, clock: "1:40", watch_s: 92, title: "", detail: "", players: [], opponent: null,
  });
  const match = (id: number, ...moments: ReviewMoment[]): ReviewMatch => ({
    id, number: id, label: `M${id}`, map: "Bermuda", placement: 5, kills: 2, downs_taken: 4,
    eliminated_s: 900, eliminated_clock: "15:00", wiped_by: "Bravo", has_tracks: true, moments,
  });

  it("lists only mistakes that came back in two or more matches", () => {
    const day = [
      match(1, moment("alone"), moment("alone"), moment("zone"), moment("trade", true)),
      match(2, moment("alone"), moment("third_party")),
      match(3, moment("third_party"), moment("trade", true)),
    ];
    assert.deepEqual(repeatedMistakes(day), [
      { kind: "alone", label: "Alone", matches: 2 },
      { kind: "third_party", label: "Third party", matches: 2 },
    ]);
  });

  it("says how a match ended", () => {
    assert.equal(finishText({ placement: 1, eliminated_clock: null, wiped_by: null }), "Booyah");
    assert.equal(finishText({ placement: 4, eliminated_clock: "15:17", wiped_by: "NOOBZ" }), "#4 · out at 15:17 to NOOBZ");
    assert.equal(finishText({ placement: 9, eliminated_clock: null, wiped_by: null }), "#9");
  });
});
