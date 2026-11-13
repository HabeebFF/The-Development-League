import type { Me } from "./api";

/** Where to go after signing in when no page asked for one: staff to Staff, teams to their
 * area, and fans (no team) to the home page. */
export function homeFor(me: Pick<Me, "staff_role"> & { memberships?: unknown[] }): string {
  if (me.staff_role) return "/staff";
  return me.memberships && me.memberships.length === 0 ? "/" : "/team";
}

/** Pages anyone can open without signing in: signing in, invites, password resets, privacy. */
export function isOpenPath(path: string): boolean {
  return /^\/(auth|invite|privacy)(\/|$)/.test(path);
}

/** League pages visitors can read without an account while the site is public. */
export function isPublicPath(path: string): boolean {
  return path === "/" || /^\/(standings|results|teams|matches|awards|players|kills|maps|ratings|cards|protection-points|predict|shop)(\/|$)/.test(path);
}

/**
 * Which week of the season a day falls in, counting the season's first day as week 1.
 * Null when either date is missing or the day is before the season starts.
 */
export function seasonWeek(startsOn: string | null, day: string | null): number | null {
  if (!startsOn || !day) return null;
  const start = Date.parse(`${startsOn.slice(0, 10)}T00:00:00Z`);
  const on = Date.parse(`${day.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(start) || Number.isNaN(on) || on < start) return null;
  return Math.floor((on - start) / (7 * 86400_000)) + 1;
}

/** The podium order for the top three: 2nd, 1st, 3rd (so 1st stands in the middle). */
export function podiumOrder<T extends { rank: number }>(rows: T[]): T[] {
  const top = rows.filter((r) => r.rank >= 1 && r.rank <= 3).sort((a, b) => a.rank - b.rank);
  if (top.length < 3) return top;
  return [top[1], top[0], top[2]];
}
