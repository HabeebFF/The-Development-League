// DC earned by playing (kills, Booyah, MVP, turning up): shapes and small helpers.

export type MatchEarning = {
  match_id: number;
  day: string;
  date: string | null;
  number: number;
  kills: number;
  booyah: boolean;
  mvp: boolean;
  amount: number;
};

export type MyEarnings =
  | { linked: false }
  | {
      linked: true;
      player_id: number;
      total: number;
      this_month: number;
      waiting: number;
      latest: MatchEarning[];
    };

export type DcSettings = {
  rewards_enabled: boolean;
  per_kill: number;
  booyah: number;
  mvp: number;
  played: number;
  start_date: string;
  on: boolean;
};

export const dc = (n: number) => `${n.toLocaleString("en-GB")} DC`;

/** "3 kills · Booyah · MVP" (or "played"). */
export function breakdown(
  e: Pick<MatchEarning, "kills" | "booyah" | "mvp">,
): string {
  const parts: string[] = [];
  if (e.kills) parts.push(`${e.kills} kill${e.kills === 1 ? "" : "s"}`);
  if (e.booyah) parts.push("Booyah");
  if (e.mvp) parts.push("MVP");
  return parts.length ? parts.join(" · ") : "played";
}

// -- Ranks --------------------------------------------------------------------------------------

export type RankStep = { key: string; name: string; min: number };
export type TeamDc = {
  team_id: number;
  name: string;
  slug: string;
  dc: number;
};
export type DcKing = {
  month: string;
  player_id: number;
  name: string;
  photo: string | null;
  team: { name: string; slug: string } | null;
  earned: number;
  from_matches: number;
};
export type DcBoard = {
  steps: RankStep[];
  initial: number;
  players: Record<string, number>;
  teams: TeamDc[];
  king: DcKing | null;
  priority: {
    team_id: number;
    name: string;
    slug: string;
    dc: number;
    week_of: string;
  } | null;
};

/** The highest rank ``earned`` reaches, or null (a Rookie: no badge). */
export function rankFor(earned: number, steps: RankStep[]): RankStep | null {
  let best: RankStep | null = null;
  for (const s of [...steps].sort((a, b) => a.min - b.min))
    if (earned >= s.min) best = s;
  return best;
}

/** The next rank up and how much DC is still needed, or null at the top. */
export function nextRank(
  earned: number,
  steps: RankStep[],
): { step: RankStep; need: number } | null {
  const next = [...steps]
    .sort((a, b) => a.min - b.min)
    .find((s) => s.min > earned);
  return next ? { step: next, need: next.min - earned } : null;
}

/** "NOVEMBER" for the month a DC King won. */
export function kingMonth(iso: string): string {
  return new Date(`${iso.slice(0, 10)}T12:00:00Z`)
    .toLocaleDateString("en-GB", { month: "long", timeZone: "UTC" })
    .toUpperCase();
}

/** Gold, silver, bronze coins for the top three teams of the month. */
export function teamCoin(
  teams: TeamDc[],
  teamId: number | null | undefined,
): 1 | 2 | 3 | null {
  if (teamId == null) return null;
  const i = teams.slice(0, 3).findIndex((t) => t.team_id === teamId);
  return i === -1 ? null : ((i + 1) as 1 | 2 | 3);
}

// -- Perks --------------------------------------------------------------------------------------

export type PerkKey = "BANNER" | "THEME" | "SHOUTOUT" | "PIN" | "NAME_COLOUR";
export type Perk = {
  key: PerkKey;
  name: string;
  price: number;
  days: number | null;
  for_team: boolean;
  enabled: boolean;
};
export type PerkPurchase = {
  id: number;
  key: PerkKey;
  name: string;
  status: "PENDING" | "ACTIVE" | "REJECTED" | "REMOVED" | "REPLACED";
  status_label: string;
  price: number;
  from_pot: boolean;
  data: Record<string, string | number | null>;
  image: string | null;
  starts_at: string | null;
  ends_at: string | null;
  player: string | null;
  team: string | null;
  buyer: string | null;
  review_note: string;
  created_at: string;
};
export type PerksPage = {
  perks: Perk[];
  name_colours: string[];
  me: {
    balance: number;
    player_id: number;
    team: { id: number; name: string; slug: string } | null;
    pot: number;
    pot_entries: { amount: number; note: string; by: string; at: string }[];
    can_spend_pot: boolean;
    purchases: PerkPurchase[];
  } | null;
};
export type Pin = {
  match_id: number;
  label: string;
  at_s: number | null;
  note: string;
};
export type LivePerks = {
  shoutouts: {
    id: number;
    text: string;
    player_id: number | null;
    name: string;
    team: string | null;
  }[];
  name_colours: Record<string, string>;
  banners: Record<string, string>;
  pins: Record<string, Pin>;
};

export const PERK_TEXT: Record<PerkKey, string> = {
  BANNER: "Your own banner across the top of your team page.",
  THEME: "Pick your team's two colours for the team page, cards and standings.",
  SHOUTOUT:
    "A line on the home page for a day (staff check it first; turned down = refunded).",
  PIN: "Pin your best moment to your card page, with the time in the match.",
  NAME_COLOUR: "Your name in colour on the kill list and ratings for a week.",
};

/** "12:05" from seconds; "" for none. */
export function clockTime(s: number | null | undefined): string {
  if (s == null) return "";
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Seconds from "12:05" or "725"; null when blank or unreadable. */
export function parseClock(text: string): number | null {
  const t = text.trim();
  if (!t) return null;
  const m = /^(\d{1,2}):([0-5]\d)$/.exec(t);
  if (m) return Number(m[1]) * 60 + Number(m[2]);
  return /^\d+$/.test(t) ? Number(t) : null;
}
