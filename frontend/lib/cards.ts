// FUT style player cards (``/cards``), out every Saturday at 11am (Lagos) for the Saturday to Friday week before.

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
  tier: "gold" | "silver" | "bronze" | "totw" | "totm";
  /** Awards won that week: player, rusher, sniper, grenader. */
  totw: string[];
  /** On a Team of the Month card: the award it stands for. */
  totm?: string;
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

export type TeamOfMonth = {
  month: string | null;
  end: string | null;
  /** False while the month is still being played: the winners can change. */
  finished?: boolean;
  previous: string | null;
  next: string | null;
  slots: {
    award: string;
    title: string;
    detail: string;
    card: PlayerCard | null;
  }[];
};

export type CardDetail = PlayerCard & {
  history: { week: string; overall: number; role: Role }[];
};

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

export const AWARD_NAMES: Record<string, string> = {
  player: "Top player",
  rusher: "Top rusher",
  sniper: "Top sniper",
  grenader: "Top grenader",
};

/** "Team of the Week: Top player, Top sniper". */
export function totwText(totw: string[]): string {
  return totw.length
    ? `Team of the Week: ${totw.map((k) => AWARD_NAMES[k] ?? k).join(", ")}`
    : "";
}

/** "October 2026" for a month starting on ``start``. */
export function monthLabel(start: string): string {
  return new Date(`${start}T00:00:00`).toLocaleDateString("en-GB", {
    month: "long",
    year: "numeric",
  });
}

/** "5 – 11 Oct" for a card week starting on Saturday ``start``. */
export function weekLabel(start: string): string {
  const from = new Date(`${start}T00:00:00`);
  const to = new Date(from);
  to.setDate(from.getDate() + 6);
  const sameMonth = from.getMonth() === to.getMonth();
  const a = from.toLocaleDateString(
    "en-GB",
    sameMonth ? { day: "numeric" } : { day: "numeric", month: "short" },
  );
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
export const TIER_COLORS: Record<
  PlayerCard["tier"],
  [string, string, string, string]
> = {
  gold: ["#f6d36b", "#a8781c", "#1d1405", "#fff3c4"],
  silver: ["#e3e8ef", "#7d8796", "#11151c", "#ffffff"],
  bronze: ["#e0a46d", "#7b4520", "#1e0f05", "#ffd9b5"],
  totw: ["#1a1d29", "#07080c", "#f2f3f7", "#ff5a1f"],
  totm: ["#24124a", "#090414", "#f7e6b4", "#f2c14e"],
};

export const TIER_LABELS: Record<PlayerCard["tier"], string> = {
  gold: "Gold",
  silver: "Silver",
  bronze: "Bronze",
  totw: "Team of the Week",
  totm: "Team of the Month",
};

/** Cards come out every Saturday at 11:00 in Lagos, which is 10:00 UTC. */
export const RELEASE_UTC = { weekday: 6, hour: 10 };

/** When the next cards come out, after ``now``. */
export function nextRelease(now: Date): Date {
  const out = new Date(
    Date.UTC(
      now.getUTCFullYear(),
      now.getUTCMonth(),
      now.getUTCDate(),
      RELEASE_UTC.hour,
    ),
  );
  out.setUTCDate(
    out.getUTCDate() + ((RELEASE_UTC.weekday - out.getUTCDay() + 7) % 7),
  );
  if (out <= now) out.setUTCDate(out.getUTCDate() + 7);
  return out;
}

/** Days, hours, minutes and seconds left until ``to``. */
export function countdown(
  now: Date,
  to: Date,
): { d: number; h: number; m: number; s: number } {
  const left = Math.max(0, Math.floor((to.getTime() - now.getTime()) / 1000));
  return {
    d: Math.floor(left / 86400),
    h: Math.floor(left / 3600) % 24,
    m: Math.floor(left / 60) % 60,
    s: left % 60,
  };
}
