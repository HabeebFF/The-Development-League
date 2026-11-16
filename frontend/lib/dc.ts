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
