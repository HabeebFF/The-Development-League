import assert from "node:assert/strict";
import { test } from "node:test";

import { canWatchMatch } from "./watch.ts";

test("only the teams that played can watch a match", () => {
  const played = [1, 2];
  assert.equal(canWatchMatch(null, played), false); // visitor
  assert.equal(canWatchMatch({ can_watch_replays: false, scrim_team_ids: [] }, played), false); // fan
  assert.equal(canWatchMatch({ can_watch_replays: true, scrim_team_ids: [2] }, played), true);
  assert.equal(canWatchMatch({ can_watch_replays: true, scrim_team_ids: [3] }, played), false);
  // Staff, or a team staff allowed to watch every match.
  assert.equal(canWatchMatch({ can_watch_replays: true, scrim_team_ids: null }, played), true);
});
