// Top performers and weapons on each map (``/maps``).

import { periodLabel } from "./awards.ts";
import type { TeamRef } from "./api";
import type { KillRow } from "./kills";

export type MapPeriod = "all" | "month" | "week";

export type MapLeader = { player_id: number; player: string; team: TeamRef | null; value: number; matches: number };

export type MapStats = {
  period: MapPeriod;
  start: string | null;
  end: string | null;
  previous: string | null;
  next: string | null;
  maps: { slug: string; name: string; matches: number }[];
  map: { slug: string; name: string; image: string | null } | null;
  matches: number;
  kills: number;
  /** Matches on the map before an average rating or damage counts. */
  min_matches: number;
  fraggers: KillRow[];
  ratings: MapLeader[];
  damage: MapLeader[];
  weapons: { id: number; name: string; kills: number; knocks: number; uses: number; share: number }[];
  teams: { team: TeamRef; matches: number; booyahs: number; avg_placement: number }[];
};

/** The API path for a map (null: the busiest one) over a period, at ``date`` or the latest. */
export function mapStatsPath(map: string | null, period: MapPeriod, date: string | null): string {
  const q = new URLSearchParams({ period });
  if (map) q.set("map", map);
  if (date && period !== "all") q.set("date", date);
  return `/map-stats?${q}`;
}

/** "All time", "5 – 11 Oct" or "October 2026". */
export function mapPeriodLabel(s: Pick<MapStats, "period" | "start" | "end">): string {
  if (s.period === "all" || !s.start || !s.end) return "All time";
  return periodLabel({ period: s.period, start: s.start, end: s.end });
}
