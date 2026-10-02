import type { Me } from "./api";

/** Where to go after signing in when no page asked for one: staff to Staff, teams to their area. */
export function homeFor(me: Pick<Me, "staff_role">): string {
  return me.staff_role ? "/staff" : "/team";
}

/** Pages anyone can open without signing in: signing in, invites and password resets. */
export function isOpenPath(path: string): boolean {
  return /^\/(auth|invite)(\/|$)/.test(path);
}
