// Kill lists for a match, a session (match day), a week or a month (``/kills``).

import { periodLabel } from "./awards.ts";
import type { TeamRef } from "./api";

export type KillRow = {
  rank: number;
  player: string;
  player_id: number;
  team: TeamRef | null;
  kills: number;
  knocks: number;
  headshots: number;
  /** Damage dealt to enemies; null when none of the player's matches had a replay .bin. */
  damage: number | null;
  matches: number;
};

export type KillScope = "match" | "session" | "week" | "month";

export type KillList = {
  scope: KillScope;
  matches: number;
  kills: number;
  players: KillRow[];
  // Sessions: the match day; ``previous``/``next`` are match day ids.
  session?: { id: number; title: string; date: string | null } | null;
  // Weeks and months: the period; ``previous``/``next`` are any day in it.
  start?: string;
  end?: string;
  previous?: number | string | null;
  next?: number | string | null;
};

/** The API path for a scope, at ``at`` (a match day id or a date) or the latest one. */
export function killsPath(scope: Exclude<KillScope, "match">, at: number | string | null): string {
  if (scope === "session") return `/kills?session=${at ?? "latest"}`;
  return `/kills?period=${scope}${at ? `&date=${at}` : ""}`;
}

/** What the list covers: "TDL DAY 12 8PM", "5 – 11 Oct" or "October 2026". */
export function killsLabel(k: KillList): string {
  if (k.scope === "session") return k.session?.title ?? "No sessions yet";
  if ((k.scope === "week" || k.scope === "month") && k.start && k.end)
    return periodLabel({ period: k.scope, start: k.start, end: k.end });
  return "";
}
