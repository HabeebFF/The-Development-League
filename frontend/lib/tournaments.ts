// Tournaments: a cup with its own table, cash prizes (shown only) and DC prizes (paid on confirm).

export type TTeam = { id: number; name: string; slug: string; tag: string; logo: string | null; primary_color: string };

export type Prize = {
  key: string;
  label: string;
  cash: number;
  dc: number;
  /** "5th to 8th": the amounts are for each place. */
  each: boolean;
  cash_paid: boolean;
  winners: { place: number | null; team: TTeam | null; players: string[] }[];
};

export type Tournament = {
  id: number;
  name: string;
  slug: string;
  season: string;
  stages: { id: number; name: string }[];
  starts_on: string | null;
  ends_on: string | null;
  format_note: string;
  keyword: string;
  status: "upcoming" | "live" | "finished" | "cancelled";
  planned_matches: number;
  matches: number;
  teams: TTeam[];
  total_cash: number;
  total_dc: number;
  prizes: Prize[];
  confirmed_at: string | null;
  cancelled_at: string | null;
  registration: Registration;
  entries: Entry[];
};

/** Registration for the qualifier: "off" when the tournament has no qualifier or no dates. */
export type RegState = "off" | "soon" | "open" | "closed" | "cancelled";

export type Registration = {
  state: RegState;
  opens_at: string | null;
  closes_at: string | null;
  fee: number;
  places: number;
  taken: number;
  waitlist: number;
  invite_count: number;
  qualify_count: number;
  invited_at: string | null;
  advanced_at: string | null;
  qualifier: { id: number; name: string } | null;
  final: { id: number; name: string };
};

export type EntryVia = "INVITED" | "REGISTERED" | "QUALIFIED" | "STAFF";
export type EntryStatus = "IN" | "WAITLIST" | "WITHDRAWN" | "REMOVED";

export type Entry = {
  id: number;
  team: TTeam;
  stage: number;
  via: EntryVia;
  status: EntryStatus;
  note: string;
  /** Staff only. */
  fee_paid?: number;
  refunded?: number;
  paid_from?: "" | "WALLET" | "POT";
  paid_by?: string | null;
  registered_by?: string | null;
  created_at?: string;
};

/** The signed-in person's team in a tournament and what they can do. */
export type MyEntry = {
  registration: Registration;
  team: TTeam | null;
  entry: (Entry & { stage_name: string }) | null;
  can_register: boolean;
  can_use_pot: boolean;
  pot?: number;
  wallet?: number | null;
  pays?: boolean;
};

export const VIA_LABEL: Record<EntryVia, string> = {
  INVITED: "Invited",
  REGISTERED: "Registered",
  QUALIFIED: "Qualified",
  STAFF: "Added by staff",
};

/** What a team's place says, e.g. "Invited to the Grand final" or "On the waitlist". */
export function entryText(e: MyEntry["entry"]): string {
  if (!e) return "Not registered";
  if (e.status === "WAITLIST") return "On the waitlist";
  if (e.via === "INVITED") return `Invited to the ${e.stage_name}`;
  if (e.via === "QUALIFIED") return `Qualified for the ${e.stage_name}`;
  return `In the ${e.stage_name}`;
}

/** "Wed 25 Nov, 8:00pm" style times in Lagos. */
export function when(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const day = d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "Africa/Lagos" });
  const time = d.toLocaleTimeString("en-GB", { hour: "numeric", minute: "2-digit", hour12: true, timeZone: "Africa/Lagos" }).replace(/\s/g, "");
  return `${day}, ${time}`;
}

/** The line under the registration heading. */
export function regText(r: Registration): string {
  switch (r.state) {
    case "soon":
      return `Registration opens ${when(r.opens_at)}`;
    case "open":
      return `Registration closes ${when(r.closes_at)}`;
    case "closed":
      return "Registration has closed";
    case "cancelled":
      return "This tournament was cancelled. Every entry fee was refunded.";
    default:
      return "";
  }
}

/** Places left in the qualifier (0 when full: new teams join the waitlist). */
export function placesLeft(r: Registration): number {
  return Math.max(r.places - r.taken, 0);
}

export type TournamentSummary = {
  name: string;
  slug: string;
  starts_on: string | null;
  ends_on: string | null;
  status: Tournament["status"];
  keyword: string;
  /** Where new uploads go: the qualifier until its teams are sent through, then the final. */
  stage: number;
  stage_ids: number[];
  season: string;
  registration: RegState;
};

export type Share = { player_id: number; player: string; amount: number; has_account: boolean };
export type PreviewPrize = {
  key: string;
  label: string;
  cash: number;
  dc: number;
  winners: { place?: number; team: { id: number; name: string } | null; player?: string; detail?: string; points?: number; shares: Share[] }[];
};
export type Preview = {
  confirmed: false;
  matches: number;
  planned_matches: number;
  ready: boolean;
  prizes: PreviewPrize[];
  total_dc: number;
  no_account: number;
  igl_choices: { id: number; name: string }[];
};
export type Paid = {
  confirmed: true;
  confirmed_at: string;
  payouts: { label: string; player: string; team: string | null; amount: number; paid: boolean }[];
};

export function naira(n: number): string {
  return `₦${n.toLocaleString("en-GB")}`;
}

export function dc(n: number): string {
  return `${n.toLocaleString("en-GB")} DC`;
}

/** The tournament a room or match day name belongs to, by its keyword ("CUP"), else null. */
export function tournamentFor<T extends { keyword: string; status: string }>(name: string, list: T[]): T | null {
  const text = name.toUpperCase();
  return list.find((t) => t.status !== "finished" && t.status !== "cancelled" && t.keyword.trim() && text.includes(t.keyword.trim().toUpperCase())) ?? null;
}

/** Dates as "16 to 17 Nov" (or one day, or nothing). */
export function dateSpan(from: string | null, to: string | null): string {
  const fmt = (d: string, month: boolean) =>
    new Date(`${d.slice(0, 10)}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: month ? "short" : undefined, timeZone: "UTC" });
  if (!from) return "";
  if (!to || to === from) return fmt(from, true);
  const sameMonth = from.slice(0, 7) === to.slice(0, 7);
  return `${fmt(from, !sameMonth)} to ${fmt(to, true)}`;
}
