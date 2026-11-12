// Public league data: seasons, standings, results and teams.

import type { MatchDay, MatchSummary, Paged, TeamRef } from "./api";

export type { TeamRef };

export type Team = TeamRef & { secondary_color: string | null; socials: Record<string, string> };

type PlayerRef = { id: number; game_uid: string; display_name: string };

/** One current player on a team page, with their numbers for the team this season. */
export type RosterPlayer = {
  player: PlayerRef;
  role: string;
  joined_on: string | null;
  /** False when staff haven't added them: the match logs show them playing for the team. */
  on_roster: boolean;
  photo: string | null;
  cutout: boolean;
  card: { overall: number; tier: "gold" | "silver" | "bronze"; role: string; role_label: string; week: string } | null;
  matches: number;
  kills: number;
  knocks: number;
  headshots: number;
  hs_pct: number | null;
  damage: number | null;
  avg_rating: number | null;
  main_weapon: { id: number; name: string; uses: number; share: number } | null;
};

export type TeamDetail = Team & {
  roster: RosterPlayer[];
  former: { player: PlayerRef; role: string; left_on: string | null; matches: number }[];
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
  /** From the replay .bin; null when the match was uploaded without one. */
  damage_dealt: number | null;
  damage_taken: number | null;
  zone_damage: number | null;
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

/** Played match days, newest first (by date, then day number; undated days count as oldest). */
export function playedNewestFirst<T extends Pick<MatchDay, "matches" | "date" | "number">>(days: T[]): T[] {
  return days
    .filter((d) => d.matches.some((m) => m.played))
    .sort((a, b) => (b.date ?? "").localeCompare(a.date ?? "") || b.number - a.number);
}

/** The newest match day with at least one played match. */
export function latestPlayed<T extends Pick<MatchDay, "matches" | "date" | "number">>(days: T[]): T | null {
  return playedNewestFirst(days)[0] ?? null;
}

export function mapName(slug: string | null): string {
  if (!slug) return "Unknown map";
  return slug.charAt(0).toUpperCase() + slug.slice(1);
}

/**
 * How many places each team moved in the overall table because of the latest match day: the
 * overall table now against the same table with that day taken out (points, then Booyahs, then
 * kills). Positive is up. Teams that only played on the latest day have no movement (new).
 */
export function overallMovement(overall: StandingRow[], latestDay: StandingRow[]): Map<number, number | null> {
  const day = new Map(latestDay.map((r) => [r.team.id, r]));
  const before = overall
    .map((r) => {
      const d = day.get(r.team.id);
      return {
        id: r.team.id,
        played: r.matches_played - (d?.matches_played ?? 0),
        points: r.total_points - (d?.total_points ?? 0),
        booyahs: r.booyahs - (d?.booyahs ?? 0),
        kills: r.kills - (d?.kills ?? 0),
      };
    })
    .filter((r) => r.played > 0)
    .sort((a, b) => b.points - a.points || b.booyahs - a.booyahs || b.kills - a.kills);
  const was = new Map(before.map((r, i) => [r.id, i + 1]));
  return new Map(overall.map((r) => [r.team.id, was.has(r.team.id) ? was.get(r.team.id)! - r.rank : null]));
}
