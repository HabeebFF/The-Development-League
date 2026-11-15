// Tournaments: a cup with its own table, cash prizes (shown only) and DC prizes (paid on confirm).

export type TTeam = { id: number; name: string; slug: string; tag: string };

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
  status: "upcoming" | "live" | "finished";
  planned_matches: number;
  matches: number;
  teams: TTeam[];
  total_cash: number;
  total_dc: number;
  prizes: Prize[];
  confirmed_at: string | null;
};

export type TournamentSummary = {
  name: string;
  slug: string;
  starts_on: string | null;
  ends_on: string | null;
  status: Tournament["status"];
  keyword: string;
  stage: number;
  season: string;
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
  return list.find((t) => t.status !== "finished" && t.keyword.trim() && text.includes(t.keyword.trim().toUpperCase())) ?? null;
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
