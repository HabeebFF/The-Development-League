import assert from "node:assert/strict";
import { test } from "node:test";

import { photoProblem, requestLine, type PhotoRequest } from "./photos.ts";

const base: PhotoRequest = { id: 1, status: "PENDING", image: null, reason: "", created_at: "", reviewed_at: null };

test("requestLine says where the photo stands", () => {
  assert.equal(requestLine(null), null);
  assert.match(requestLine(base)!, /waiting for league staff/);
  assert.match(requestLine({ ...base, status: "APPROVED" })!, /approved/);
  assert.match(requestLine({ ...base, status: "REJECTED", reason: "Blurry" })!, /: Blurry$/);
  assert.match(requestLine({ ...base, status: "REJECTED" })!, /send another/);
  assert.equal(requestLine({ ...base, status: "WITHDRAWN" }), null);
});

test("photoProblem checks type and size", () => {
  assert.equal(photoProblem({ size: 1000, type: "image/png" }), null);
  assert.match(photoProblem({ size: 1000, type: "image/gif" })!, /JPEG/);
  assert.match(photoProblem({ size: 6 * 1024 * 1024, type: "image/jpeg" })!, /5 MB/);
});
