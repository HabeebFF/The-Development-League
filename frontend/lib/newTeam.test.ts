import assert from "node:assert/strict";
import { test } from "node:test";

import { blankForm, cleanUid, countryName, filledRows, formData, formFrom, setIgl, statusText, type NewTeam } from "./newTeam.ts";

test("a blank form has the minimum number of empty rows", () => {
  const form = blankForm(4);
  assert.equal(form.roster.length, 4);
  assert.equal(form.country, "NG");
  assert.ok(form.roster.every((r) => r.uid === "" && !r.igl));
});

test("only one IGL", () => {
  const rows = blankForm(4).roster;
  const one = setIgl(rows, 1, true);
  assert.deepEqual(
    one.map((r) => r.igl),
    [false, true, false, false],
  );
  const moved = setIgl(one, 3, true);
  assert.deepEqual(
    moved.map((r) => r.igl),
    [false, false, false, true],
  );
  assert.ok(setIgl(moved, 3, false).every((r) => !r.igl));
});

test("UIDs keep digits only", () => {
  assert.equal(cleanUid(" 2063 288-734 "), "2063288734");
  assert.equal(cleanUid("1".repeat(30)).length, 20);
});

test("blank rows are left out when sending", () => {
  const form = blankForm(5);
  form.name = " Nairobi Kings ";
  form.tag = "nbk";
  form.roster[0] = { uid: "1000001", name: "NBK ACE", role: "RUSHER", igl: true };
  assert.equal(filledRows(form.roster).length, 1);
  const data = formData(form, null);
  assert.equal(data.get("name"), "Nairobi Kings");
  assert.equal(data.get("tag"), "NBK");
  assert.deepEqual(JSON.parse(String(data.get("roster"))), [form.roster[0]]);
  assert.equal(data.get("logo"), null);
});

test("editing a sent team starts from what was sent", () => {
  const team = {
    name: "Nairobi Kings",
    tag: "NBK",
    country: "KE",
    lobby_name: "",
    contact: "+254",
    players: [{ uid: "1", name: "A", role: "RUSHER", igl: false, error: null, flag: null, known: null }],
  } as unknown as NewTeam;
  const form = formFrom(team);
  assert.deepEqual(form.roster, [{ uid: "1", name: "A", role: "RUSHER", igl: false }]);
  assert.equal(form.country, "KE");
});

test("status wording", () => {
  assert.equal(statusText({ status: "PENDING", review_note: "" }).title, "Waiting for TDL staff");
  assert.match(statusText({ status: "REJECTED", review_note: "Send a screenshot" }).body, /Send a screenshot/);
  assert.equal(countryName("GH"), "Ghana");
  assert.equal(countryName("XX"), "XX");
});
