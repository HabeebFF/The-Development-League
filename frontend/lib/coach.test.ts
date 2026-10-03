import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { dataText, parseData } from "./coach.ts";

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
