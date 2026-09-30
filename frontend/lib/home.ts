import type { Me } from "./api";

/** Where to go after signing in when no page asked for one: staff to Staff, teams to their area. */
export function homeFor(me: Pick<Me, "staff_role">): string {
  return me.staff_role ? "/staff" : "/team";
}
