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
  tier: "gold" | "silver" | "bronze" | "totw" | "totm" | "rising" | "icon";
  /** Awards won that week: player, rusher, sniper, grenader. */
  totw: string[];
  /** A Rising Star (a big jump in overall) or an Icon (95+ weeks in a row). */
  special?: "" | "rising_star" | "icon";
  /** A Rising Star's jump since their last card. */
  rise?: number | null;
  /** Back-to-back weeks at the Icon rating, this one included. */
  streak?: number;
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
  /** The newest month: its cards start face down. */
  newest?: boolean;
  previous: string | null;
  next: string | null;
  slots: AwardSlot[];
};

export type AwardSlot = {
  award: string;
  title: string;
  detail: string;
  card: PlayerCard | null;
};

export type IconRun = {
  player_id: number;
  name: string;
  photo: string | null;
  from: string;
  to: string;
  weeks: number;
  best: number;
  /** Still an Icon on the newest cards. */
  current: boolean;
};

/** A week's special cards: Team of the Week, Rising Stars and Icons. */
export type CardSpecials = {
  week: string | null;
  end: string | null;
  previous: string | null;
  next: string | null;
  /** The newest week: its Team of the Week starts face down. */
  newest: boolean;
  team_of_week: AwardSlot[];
  rising: PlayerCard[];
  icons: PlayerCard[];
  hall: IconRun[];
  /** What it takes (staff can change these). */
  bars: { rising_min: number; icon_min: number; icon_weeks: number };
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

/** "26 Sep to 9 Oct" for card weeks ``from`` to ``to`` (both Saturdays), Friday included. */
export function runLabel(from: string, to: string): string {
  const end = new Date(`${to}T00:00:00`);
  end.setDate(end.getDate() + 6);
  const short = (d: Date) =>
    d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  return `${short(new Date(`${from}T00:00:00`))} to ${short(end)}`;
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
  rising: ["#0f6b5f", "#04201f", "#e9fff8", "#3ee6b0"],
  icon: ["#fbf8ee", "#cdb67a", "#241a04", "#a8811f"],
};

export const TIER_LABELS: Record<PlayerCard["tier"], string> = {
  gold: "Gold",
  silver: "Silver",
  bronze: "Bronze",
  totw: "Team of the Week",
  totm: "Team of the Month",
  rising: "Rising Star",
  icon: "Icon",
};

/** The small line at the foot of a card. */
export function cardFooter(card: PlayerCard): string {
  if (card.tier === "totm")
    return `TOTM · ${AWARD_NAMES[card.totm ?? ""] ?? "Team of the month"}`;
  if (card.tier === "totw") return "Team of the week";
  if (card.tier === "icon") return "Icon";
  if (card.tier === "rising")
    return card.rise ? `Rising star · +${card.rise}` : "Rising star";
  return card.stale ? "Not enough matches" : "TDL";
}

// Face-down cards: which ones this browser has already turned over.
const FLIPPED_KEY = "tdl-flipped-cards";

/** The id a face-down card is remembered by: a new winner starts face down again. */
export function flipId(
  kind: "totw" | "totm",
  period: string,
  award: string,
  playerId: number,
): string {
  return `${kind}:${period}:${award}:${playerId}`;
}

export function readFlipped(): Set<string> {
  try {
    const raw = window.localStorage.getItem(FLIPPED_KEY);
    const ids = raw ? JSON.parse(raw) : [];
    return new Set(
      Array.isArray(ids) ? ids.filter((x) => typeof x === "string") : [],
    );
  } catch {
    return new Set();
  }
}

export function saveFlipped(ids: Set<string>): void {
  try {
    // Only the newest few hundred: old weeks show face up anyway.
    window.localStorage.setItem(
      FLIPPED_KEY,
      JSON.stringify([...ids].slice(-300)),
    );
  } catch {
    // Private windows and blocked storage: the cards just start face down next time.
  }
}

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
