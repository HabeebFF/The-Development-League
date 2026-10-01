// Public league data: seasons, standings, results and teams.

import type { MatchDay, MatchSummary, Paged, TeamRef } from "./api";

export type { TeamRef };

export type Team = TeamRef & { secondary_color: string | null; socials: Record<string, string> };

export type TeamDetail = Team & {
  roster: { player: { id: number; game_uid: string; display_name: string }; role: string; joined_on: string | null }[];
};

export type Season = {
  id: number;
  name: string;
  slug: string;
  starts_on: string | null;
  ends_on: string | null;
  is_active: boolean;
};

export type SeasonDetail = Season & {
  scoring: { name: string; placement_points: Record<string, number>; default_points: number; points_per_kill: number } | null;
  tiebreakers: string[];
  stages: { id: number; name: string; order: number; kind: string; groups: { id: number; name: string; teams: TeamRef[] }[] }[];
};

export type StandingRow = {
  rank: number;
  team: TeamRef;
  matches_played: number;
  booyahs: number;
  kills: number;
  placement_points: number;
  kill_points: number;
  total_points: number;
  avg_placement: number | null;
  last_match_points: number | null;
  form: number[];
};

export type Standings = { season: string; scope: string; updated_at: string | null; rows: StandingRow[] };

export type PlayerResult = {
  game_uid: string;
  display_name: string;
  kills: number;
  knocks: number;
  headshot_knocks: number;
  deaths: number;
  respawns: number;
  is_mvp: boolean;
};

export type TeamResult = {
  placement: number;
  team: TeamRef;
  in_game_name: string;
  booyah: boolean;
  kills: number;
  placement_points: number;
  kill_points: number;
  total_points: number;
  eliminated_at_s: number | null;
  players: PlayerResult[];
};

export type MatchListItem = MatchSummary & { season: string; match_day: number };

export type MatchDetail = MatchListItem & { game_match_id: string; duration_s: number | null; results: TeamResult[] };

export type MatchDayDetail = MatchDay & { season: string; standings: StandingRow[] };

export function rows<T>(data: Paged<T> | T[]): T[] {
  return Array.isArray(data) ? data : data.results;
}

/** The season the site shows: the active one, else the newest. */
export function currentSeason(seasons: Season[]): Season | null {
  return seasons.find((s) => s.is_active) ?? seasons[0] ?? null;
}

export function dayName(day: Pick<MatchDay, "title" | "number">): string {
  return day.title || `Day ${day.number}`;
}

export function shortDate(iso: string | null): string {
  if (!iso) return "";
  // Dates without a time are calendar days: read them as local, not UTC midnight.
  const date = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? new Date(`${iso}T00:00:00`) : new Date(iso);
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function ordinal(n: number): string {
  const tens = n % 100;
  if (tens >= 11 && tens <= 13) return `${n}th`;
  return `${n}${{ 1: "st", 2: "nd", 3: "rd" }[n % 10] ?? "th"}`;
}

export function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

/** The newest match day with at least one played match. Days come oldest first. */
export function latestPlayed<T extends Pick<MatchDay, "matches">>(days: T[]): T | null {
  return [...days].reverse().find((d) => d.matches.some((m) => m.played)) ?? null;
}

export function mapName(slug: string | null): string {
  if (!slug) return "Unknown map";
  return slug.charAt(0).toUpperCase() + slug.slice(1);
}
