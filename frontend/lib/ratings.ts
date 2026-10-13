// Player ratings out of 10, like football apps (``/ratings``, match and match day pages).

import type { TeamRef } from "./api";

export type Band = "red" | "orange" | "green" | "blue" | "gold";

export type MatchRatingRef = { match: number; label: string; session: string; rating: number; band: Band };

export type RatingRow = {
  rank: number;
  player: string;
  player_id: number;
  team: TeamRef | null;
  rating: number;
  band: Band;
  matches: number;
  best: number;
  kills: number;
  knocks: number;
  star?: boolean;
  ratings: MatchRatingRef[];
};

export type RatingBoard = {
  matches: number;
  need: number; // matches a Player of the Day needs
  star: number | null;
  players: RatingRow[];
};

export type DayRatings = RatingBoard & {
  date: string | null;
  previous: string | null;
  next: string | null;
  sessions: { id: number; title: string }[];
  session: number | null;
};

export type RatingPart = { key: string; label: string; count: number; points: number };

export type MatchRatings = {
  match: number;
  base: number;
  players: {
    player: string;
    player_id: number;
    team: TeamRef | null;
    rating: number;
    band: Band;
    kills: number;
    knocks: number;
    placement: number | null;
    parts: RatingPart[];
  }[];
};

export type PlayerRatings = {
  player_id: number;
  name: string;
  days: { date: string; rating: number; band: Band; matches: number }[];
  week: { rating: number; band: Band; matches: number } | null;
  month: { rating: number; band: Band; matches: number } | null;
  all: { rating: number; matches: number } | null;
};

/** Badge colours: red under 6, orange 6s, green 7s, blue 8s, gold 9 and up. */
export const BAND_CLASSES: Record<Band, string> = {
  red: "bg-[#e5484d] text-white",
  orange: "bg-[#f08c2e] text-black",
  green: "bg-[#2fb36b] text-black",
  blue: "bg-[#3b82f6] text-white",
  gold: "bg-[#f6c544] text-black",
};

/** 7 shows as "7.0", like the football apps. */
export function ratingText(r: number): string {
  return r.toFixed(1);
}

/** The API path for a day (``null`` the latest), optionally one session of it. */
export function ratingsPath(date: string | null, session: number | null = null): string {
  const q = [date ? `date=${date}` : "", session ? `session=${session}` : ""].filter(Boolean).join("&");
  return `/ratings${q ? `?${q}` : ""}`;
}

/** "+0.54" or "-0.20" for one part of a rating. */
export function pointsText(p: number): string {
  return `${p > 0 ? "+" : p < 0 ? "−" : "±"}${Math.abs(p).toFixed(2)}`;
}

/** What a part counted: "3 kills", "Team 2nd", "Alive 84% of the match". */
export function partText(p: RatingPart): string {
  if (p.key === "placement") return p.count === 1 ? "Booyah" : `Team ${ordinalOf(p.count)}`;
  if (p.key === "survival") return `Alive ${Math.round(p.count * 100)}% of the match`;
  if (p.key === "first_down") return p.label;
  return `${p.label}: ${p.count}`;
}

function ordinalOf(n: number): string {
  const tens = n % 100;
  if (tens >= 11 && tens <= 13) return `${n}th`;
  return `${n}${["th", "st", "nd", "rd"][n % 10] ?? "th"}`;
}

/** "1 match", "5 matches". */
export function matchCount(n: number): string {
  return `${n} match${n === 1 ? "" : "es"}`;
}
