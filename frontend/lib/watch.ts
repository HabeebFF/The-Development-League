import type { Me } from "./api";

/** Replays and rotations of a match are for the teams that played it, plus staff and teams
 * staff allowed to watch every match (SCRIM-VIEWING). */
export function canWatchMatch(
  me: Pick<Me, "can_watch_replays" | "scrim_team_ids"> | null | undefined,
  teamIds: number[],
): boolean {
  if (!me?.can_watch_replays) return false;
  const mine = me.scrim_team_ids;
  if (mine === null || mine === undefined) return true; // every match
  return teamIds.some((id) => mine.includes(id));
}
