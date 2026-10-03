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
