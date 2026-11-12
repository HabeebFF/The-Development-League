import type { MatchDay, MatchSummary } from "./api";
import { seasonWeek } from "./home.ts";

export type ResultsDay = { day: MatchDay; matches: MatchSummary[] };
export type ResultsDate = { date: string | null; week: number | null; days: ResultsDay[] };

/**
 * Played match days grouped by calendar date (newest first), each with its matches in order.
 * ``week`` keeps only that week of the season; ``map`` keeps only matches on that map and drops
 * sessions left with none.
 */
export function groupResults(
  days: MatchDay[],
  { startsOn = null, week = null, map = null }: { startsOn?: string | null; week?: number | null; map?: string | null } = {},
): ResultsDate[] {
  const out: ResultsDate[] = [];
  for (const day of days) {
    const w = seasonWeek(startsOn, day.date);
    if (week != null && w !== week) continue;
    const matches = [...day.matches].sort((a, b) => a.number - b.number).filter((m) => !map || m.map === map);
    if (!matches.length) continue;
    const last = out[out.length - 1];
    if (last && last.date === day.date) last.days.push({ day, matches });
    else out.push({ date: day.date, week: w, days: [{ day, matches }] });
  }
  return out;
}

/** The season weeks that have match days, newest first. */
export function resultWeeks(days: MatchDay[], startsOn: string | null): number[] {
  const weeks = new Set<number>();
  for (const d of days) {
    const w = seasonWeek(startsOn, d.date);
    if (w != null) weeks.add(w);
  }
  return [...weeks].sort((a, b) => b - a);
}

/** Maps played on any of these days, in the league's map order. */
export function resultMaps(days: MatchDay[]): string[] {
  const order = ["bermuda", "purgatory", "kalahari", "nexterra", "solara"];
  const seen = new Set(days.flatMap((d) => d.matches.map((m) => m.map).filter((m): m is string => !!m)));
  return [...order.filter((m) => seen.has(m)), ...[...seen].filter((m) => !order.includes(m)).sort()];
}
