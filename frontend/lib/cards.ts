// FUT style player cards (``/cards``), rebuilt every Monday from the weeks before.

import type { TeamRef } from "./api";

export type CardStat = {
  key: string;
  label: string;
  rating: number | null;
  /** Up or down since the player's last card; null when there's nothing to compare. */
  change: number | null;
  /** Not enough matches with this data: last week's rating, carried over. */
  stale: boolean;
  /** A grenader's extra stats. */
  extra?: boolean;
  value: string | null;
  detail: string;
};

export type PlayerCard = {
  player_id: number;
  name: string;
  photo: string | null;
  team: TeamRef | null;
  week: string;
  role: Role;
  role_label: string;
  role_suggested: boolean;
  /** What the numbers say they play as (staff may have picked another role). */
  suggested_role: Role;
  overall: number;
  overall_change: number | null;
  tier: "gold" | "silver" | "bronze" | "totw";
  /** Awards won that week: player, rusher, sniper, grenader. */
  totw: string[];
  stats: CardStat[];
  matches: number;
  week_matches: number;
  stale: boolean;
};

export type CardWeek = {
  week: string | null;
  end: string | null;
  previous: string | null;
  next: string | null;
  cards: PlayerCard[];
};

export type CardDetail = PlayerCard & { history: { week: string; overall: number; role: Role }[] };

export type Role = "RUSHER" | "GRENADER" | "SNIPER" | "ALL_ROUNDER";

export const ROLES: { key: Role; label: string; short: string }[] = [
  { key: "RUSHER", label: "Rusher", short: "RSH" },
  { key: "GRENADER", label: "Grenader", short: "NDR" },
  { key: "SNIPER", label: "Sniper", short: "SNP" },
  { key: "ALL_ROUNDER", label: "All-rounder", short: "ALL" },
];

/** The picture for players without a photo. */
export const BLANK_PHOTO = "/player-blank.svg";

export function roleShort(role: string): string {
  return ROLES.find((r) => r.key === role)?.short ?? role.slice(0, 3);
}

/** "▲ 3", "▼ 2", or "" when nothing changed (or nothing to compare). */
export function changeText(change: number | null | undefined): string {
  if (!change) return "";
  return change > 0 ? `▲ ${change}` : `▼ ${-change}`;
}

const AWARD_NAMES: Record<string, string> = {
  player: "Top player",
  rusher: "Top rusher",
  sniper: "Top sniper",
  grenader: "Top grenader",
};

/** "Team of the Week: Top player, Top sniper". */
export function totwText(totw: string[]): string {
  return totw.length ? `Team of the Week: ${totw.map((k) => AWARD_NAMES[k] ?? k).join(", ")}` : "";
}

/** "5 – 11 Oct" for a week starting on Monday ``start``. */
export function weekLabel(start: string): string {
  const from = new Date(`${start}T00:00:00`);
  const to = new Date(from);
  to.setDate(from.getDate() + 6);
  const sameMonth = from.getMonth() === to.getMonth();
  const a = from.toLocaleDateString("en-GB", sameMonth ? { day: "numeric" } : { day: "numeric", month: "short" });
  return `${a} – ${to.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`;
}

/** A file name for a saved card: "tdl-card-ace-2026-10-05.png". */
export function cardFileName(card: Pick<PlayerCard, "name" | "week">): string {
  const slug = card.name
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return `tdl-card-${slug || "player"}-${card.week}.png`;
}

/** Colours for each tier: [top of the card, bottom, text, accent line]. */
export const TIER_COLORS: Record<PlayerCard["tier"], [string, string, string, string]> = {
  gold: ["#f6d36b", "#a8781c", "#1d1405", "#fff3c4"],
  silver: ["#e3e8ef", "#7d8796", "#11151c", "#ffffff"],
  bronze: ["#e0a46d", "#7b4520", "#1e0f05", "#ffd9b5"],
  totw: ["#1a1d29", "#07080c", "#f2f3f7", "#ff5a1f"],
};

export const TIER_LABELS: Record<PlayerCard["tier"], string> = {
  gold: "Gold",
  silver: "Silver",
  bronze: "Bronze",
  totw: "Team of the Week",
};
