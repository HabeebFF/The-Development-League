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
  | { linked: true; player_id: number; total: number; this_month: number; waiting: number; latest: MatchEarning[] };

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
export function breakdown(e: Pick<MatchEarning, "kills" | "booyah" | "mvp">): string {
  const parts: string[] = [];
  if (e.kills) parts.push(`${e.kills} kill${e.kills === 1 ? "" : "s"}`);
  if (e.booyah) parts.push("Booyah");
  if (e.mvp) parts.push("MVP");
  return parts.length ? parts.join(" · ") : "played";
}

// -- Ranks --------------------------------------------------------------------------------------

export type RankStep = { key: string; name: string; min: number };
export type TeamDc = { team_id: number; name: string; slug: string; dc: number };
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
};

/** The highest rank ``earned`` reaches, or null (a Rookie: no badge). */
export function rankFor(earned: number, steps: RankStep[]): RankStep | null {
  let best: RankStep | null = null;
  for (const s of [...steps].sort((a, b) => a.min - b.min)) if (earned >= s.min) best = s;
  return best;
}

/** The next rank up and how much DC is still needed, or null at the top. */
export function nextRank(earned: number, steps: RankStep[]): { step: RankStep; need: number } | null {
  const next = [...steps].sort((a, b) => a.min - b.min).find((s) => s.min > earned);
  return next ? { step: next, need: next.min - earned } : null;
}

/** "NOVEMBER" for the month a DC King won. */
export function kingMonth(iso: string): string {
  return new Date(`${iso.slice(0, 10)}T12:00:00Z`).toLocaleDateString("en-GB", { month: "long", timeZone: "UTC" }).toUpperCase();
}

/** Gold, silver, bronze coins for the top three teams of the month. */
export function teamCoin(teams: TeamDc[], teamId: number | null | undefined): 1 | 2 | 3 | null {
  if (teamId == null) return null;
  const i = teams.slice(0, 3).findIndex((t) => t.team_id === teamId);
  return i === -1 ? null : ((i + 1) as 1 | 2 | 3);
}
