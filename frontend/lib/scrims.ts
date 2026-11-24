// Scrim registration: teams sign up for a night's 8PM and 10PM sessions (Mon, Tue, Thu, Fri).
// Sign-up opens 8:00pm Lagos time the night before and closes 6:00pm (8PM) and 8:00pm (10PM).
// It costs a DC fee (refunded on withdrawal). A full session locks and its predictions open
// at once. See backend/apps/scrims/services.py for the rules.

import type { TeamRef } from "./api";

export type Stage = "off" | "soon" | "open" | "closed" | "started";

export type Entry = {
  team: TeamRef;
  by_staff: boolean;
  /** Staff only. */
  registered_by?: string | null;
  at?: string;
};

/** A map drawn for a match (drawn when the night's sign-up opens). */
export type MapRef = { id: number; name: string; slug: string };

export type ScrimSession = {
  date: string;
  session: "8PM" | "10PM";
  stage: Stage;
  opens_at: string;
  closes_at: string;
  starts_at: string;
  max_teams: number;
  /** Full: playing teams can't withdraw, predictions are open. */
  locked: boolean;
  /** Staff called it off: fees and predictions refunded, no sign-up. */
  called_off?: boolean;
  called_off_reason?: string;
  /** DC to sign up or confirm. */
  fee: number;
  playing: Entry[];
  /** Invited by staff, place held until the team confirms. */
  invited: Entry[];
  waitlist: Entry[];
  /** Each match's map, in order: drawn when sign-up opens (empty before). */
  maps?: MapRef[];
  /** Staff only: matches in the session. */
  match_count?: number;
  /** On the team page: the team's place in it. */
  mine?: "REGISTERED" | "INVITED" | "WAITLIST" | null;
  waitlist_place?: number;
};

export type Suspended = { reason: string; until: string | null; since: string };

export type Night = { date: string | null; sessions: ScrimSession[] };

/** The public lobby: the first night shown, plus every night shown (tonight and, once its
 * sign-up opens, the next one). */
export type Nights = Night & { nights: Night[] };

export type TeamNight = Nights & {
  team: TeamRef;
  can_manage: boolean;
  suspended: Suspended | null;
  fee: number;
};

export type StaffNight = Night & { scrim_night: boolean; map_pool?: MapRef[] };

export type StaffTeam = TeamRef & {
  suspended: Suspended | null;
  /** Approved and not suspended: on the allowed list, so it can sign up. */
  allowed?: boolean;
  status?: "PENDING" | "APPROVED" | "REJECTED";
};

export type ScrimSettings = {
  weekdays: number[];
  skip_dates: string[];
  opens_at: string;
  opens_days_before: number;
  closes_at: Record<string, string>;
  max_teams: number;
  fee: number;
};

export type LogRow = {
  at: string;
  team: string;
  action: string;
  label: string;
  session: string | null;
  by: string | null;
  note: string;
};

export const TZ = "Africa/Lagos";
export const WEEKDAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

/** "6:00pm" in Lagos time. */
export function clock(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: TZ,
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  })
    .format(new Date(iso))
    .replace(/\s/g, "")
    .toLowerCase();
}

/** Today's date in Lagos, as 2026-11-16. */
export function lagosToday(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

/** "8:00pm" if it's today in Lagos, else "Wed 8:00pm". */
export function dayClock(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  if (lagosToday(d) === lagosToday(now)) return clock(iso);
  const day = new Intl.DateTimeFormat("en-GB", {
    timeZone: TZ,
    weekday: "short",
  }).format(d);
  return `${day} ${clock(iso)}`;
}

/** "1,500 DC". */
export function dc(n: number): string {
  return `${n.toLocaleString("en-GB")} DC`;
}

/** "Tonight" or "Monday 16 Nov". */
export function nightName(date: string, now: Date = new Date()): string {
  if (date === lagosToday(now)) return "Tonight";
  const d = new Date(`${date}T12:00:00Z`);
  return `${WEEKDAYS[(d.getUTCDay() + 6) % 7]} ${d.getUTCDate()} ${d.toLocaleString("en-GB", { month: "short", timeZone: "UTC" })}`;
}

/** One line on where sign-up is. */
export function stageText(
  s: Pick<ScrimSession, "stage" | "opens_at" | "closes_at" | "starts_at"> & {
    locked?: boolean;
    called_off?: boolean;
    called_off_reason?: string;
  },
  now: Date = new Date(),
): string {
  if (s.called_off)
    return `Called off${s.called_off_reason ? ` · ${s.called_off_reason}` : ""}`;
  switch (s.stage) {
    case "soon":
      return `Sign-up opens ${dayClock(s.opens_at, now)}`;
    case "open":
      return s.locked
        ? "Full · predictions open · waitlist only"
        : `Sign-up open until ${dayClock(s.closes_at, now)}`;
    case "closed":
      return `Sign-up closed · starts ${clock(s.starts_at)}`;
    case "started":
      return "Started";
    default:
      return "No scrims";
  }
}

/** "11/12" places taken, and how many are left. */
export function places(s: Pick<ScrimSession, "playing" | "max_teams">): {
  taken: string;
  left: number;
} {
  return {
    taken: `${s.playing.length}/${s.max_teams}`,
    left: Math.max(0, s.max_teams - s.playing.length),
  };
}

/** What the team sees about its own place. */
export function myStatus(s: ScrimSession): string {
  if (s.mine === "REGISTERED")
    return s.stage === "open" || s.stage === "soon"
      ? "You're in"
      : "You're playing";
  if (s.mine === "INVITED")
    return s.stage === "open" || s.stage === "soon"
      ? "Invited: confirm your place"
      : "Invite expired";
  if (s.mine === "WAITLIST") {
    const n = s.waitlist_place ?? 0;
    return s.stage === "open" ? `Waitlist, #${n}` : "Waitlisted: not playing";
  }
  return s.stage === "open"
    ? "Not signed up"
    : s.stage === "soon"
      ? "Not open yet"
      : "Not playing";
}

export type Action = "register" | "withdraw" | "confirm" | "decline";

/** The buttons a manager or linked player sees (main first), or none. */
export function actions(
  s: ScrimSession,
  canManage: boolean,
  suspended: boolean,
): Action[] {
  if (!canManage) return [];
  if (s.mine === "INVITED") {
    if (s.stage !== "open" && s.stage !== "soon") return [];
    return suspended ? ["decline"] : ["confirm", "decline"];
  }
  if (s.stage !== "open") return [];
  if (s.mine === "REGISTERED") return s.locked ? [] : ["withdraw"];
  if (s.mine) return ["withdraw"];
  return suspended ? [] : ["register"];
}

/** The main button, or null when there's nothing to press. */
export function action(
  s: ScrimSession,
  canManage: boolean,
  suspended: boolean,
): Action | null {
  return actions(s, canManage, suspended)[0] ?? null;
}

/** Where each button posts: confirming is a sign-up, declining is a withdrawal. */
export function endpoint(a: Action): "register" | "withdraw" {
  return a === "register" || a === "confirm" ? "register" : "withdraw";
}

/** The label on a button. */
export function actionLabel(
  a: Action,
  s: Pick<ScrimSession, "session" | "fee" | "locked" | "playing" | "max_teams">,
): string {
  const cost = s.fee > 0 ? ` · ${dc(s.fee)}` : "";
  switch (a) {
    case "register":
      return s.locked || s.playing.length >= s.max_teams
        ? `Join the waitlist${cost}`
        : `Sign up for ${s.session}${cost}`;
    case "confirm":
      return `Confirm my place${cost}`;
    case "decline":
      return "Decline";
    default:
      return "Withdraw";
  }
}

/** Weekdays as "Mon, Tue, Thu, Fri". */
export function weekdayList(days: number[]): string {
  return days.length
    ? [...days]
        .sort()
        .map((d) => WEEKDAYS[d].slice(0, 3))
        .join(", ")
    : "None";
}

/** "M1 Kalahari", ... for a session's drawn maps. */
export function mapLine(s: Pick<ScrimSession, "maps">): string[] {
  return (s.maps ?? []).map((m, i) => `M${i + 1} ${m.name}`);
}

/** What calling off a night (or one session) would do, per session. */
export type CallOffPlan = {
  date: string;
  sessions: {
    session: "8PM" | "10PM";
    called_off: boolean;
    teams: number;
    fees: number;
    dc: number;
    started: boolean;
    markets: number;
    bets: number;
    multiples: number;
    settled: number;
  }[];
};
