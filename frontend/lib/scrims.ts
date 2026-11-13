// Scrim registration: teams sign up for a night's 8PM and 10PM sessions (Mon, Tue, Thu, Fri).
// Sign-up opens 12:01pm Lagos time and closes 6:00pm (8PM) and 8:00pm (10PM). See
// backend/apps/scrims/services.py for the rules.

import type { TeamRef } from "./api";

export type Stage = "off" | "soon" | "open" | "closed" | "started";

export type Entry = {
  team: TeamRef;
  by_staff: boolean;
  /** Staff only. */
  registered_by?: string | null;
  at?: string;
};

export type ScrimSession = {
  date: string;
  session: "8PM" | "10PM";
  stage: Stage;
  opens_at: string;
  closes_at: string;
  starts_at: string;
  max_teams: number;
  playing: Entry[];
  waitlist: Entry[];
  /** On the team page: the team's place in it. */
  mine?: "REGISTERED" | "WAITLIST" | null;
  waitlist_place?: number;
};

export type Suspended = { reason: string; until: string | null; since: string };

export type Night = { date: string | null; sessions: ScrimSession[] };

export type TeamNight = Night & { team: TeamRef; can_manage: boolean; suspended: Suspended | null };

export type StaffNight = Night & { scrim_night: boolean };

export type StaffTeam = TeamRef & { suspended: Suspended | null };

export type ScrimSettings = {
  weekdays: number[];
  skip_dates: string[];
  opens_at: string;
  closes_at: Record<string, string>;
  max_teams: number;
};

export type LogRow = { at: string; team: string; action: string; label: string; session: string | null; by: string | null; note: string };

export const TZ = "Africa/Lagos";
export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

/** "6:00pm" in Lagos time. */
export function clock(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "numeric", minute: "2-digit", hour12: true })
    .format(new Date(iso))
    .replace(/\s/g, "")
    .toLowerCase();
}

/** Today's date in Lagos, as 2026-11-16. */
export function lagosToday(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}

/** "Tonight" or "Monday 16 Nov". */
export function nightName(date: string, now: Date = new Date()): string {
  if (date === lagosToday(now)) return "Tonight";
  const d = new Date(`${date}T12:00:00Z`);
  return `${WEEKDAYS[(d.getUTCDay() + 6) % 7]} ${d.getUTCDate()} ${d.toLocaleString("en-GB", { month: "short", timeZone: "UTC" })}`;
}

/** One line on where sign-up is. */
export function stageText(s: Pick<ScrimSession, "stage" | "opens_at" | "closes_at" | "starts_at">): string {
  switch (s.stage) {
    case "soon":
      return `Sign-up opens ${clock(s.opens_at)}`;
    case "open":
      return `Sign-up open until ${clock(s.closes_at)}`;
    case "closed":
      return `Sign-up closed · starts ${clock(s.starts_at)}`;
    case "started":
      return "Started";
    default:
      return "No scrims";
  }
}

/** "11/12" places taken, and how many are left. */
export function places(s: Pick<ScrimSession, "playing" | "max_teams">): { taken: string; left: number } {
  return { taken: `${s.playing.length}/${s.max_teams}`, left: Math.max(0, s.max_teams - s.playing.length) };
}

/** What the team sees about its own place. */
export function myStatus(s: ScrimSession): string {
  if (s.mine === "REGISTERED") return s.stage === "open" || s.stage === "soon" ? "You're in" : "You're playing";
  if (s.mine === "WAITLIST") {
    const n = s.waitlist_place ?? 0;
    return s.stage === "open" ? `Waitlist, #${n}` : "Waitlisted: not playing";
  }
  return s.stage === "open" ? "Not signed up" : s.stage === "soon" ? "Not open yet" : "Not playing";
}

/** The button a manager sees, or null when there's nothing to press. */
export function action(s: ScrimSession, canManage: boolean, suspended: boolean): "register" | "withdraw" | null {
  if (!canManage || s.stage !== "open") return null;
  if (s.mine) return "withdraw";
  return suspended ? null : "register";
}

/** Weekdays as "Mon, Tue, Thu, Fri". */
export function weekdayList(days: number[]): string {
  return days.length ? [...days].sort().map((d) => WEEKDAYS[d].slice(0, 3)).join(", ") : "None";
}
