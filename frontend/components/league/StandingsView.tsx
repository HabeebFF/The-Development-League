"use client";

import { useMemo, useState } from "react";

import EmptyState from "@/components/ui/EmptyState";
import Tabs from "@/components/ui/Tabs";
import type { MatchDay, Paged } from "@/lib/api";
import {
  currentSeason,
  dayName,
  overallMovement,
  playedNewestFirst,
  plural,
  rows,
  shortDate,
  type Season,
  type SeasonDetail,
  type Standings,
} from "@/lib/league";
import type { PPTable } from "@/lib/pp";
import { useApi } from "@/lib/useApi";

import Loading from "./Loading";
import StandingsTable from "./StandingsTable";

/** One match day's table (the latest by default), or the overall table of every day added up. */
export default function StandingsView() {
  const seasons = useApi<Paged<Season>>("/seasons?page_size=100");
  const all = seasons.data ? rows(seasons.data) : [];
  const [picked, setPicked] = useState<string | null>(null);
  const slug = picked ?? currentSeason(all)?.slug ?? null;
  // A match day id, "overall", or null for the latest day.
  const [dayId, setDayId] = useState<number | "overall" | null>(null);

  const enc = slug ? encodeURIComponent(slug) : null;
  const detail = useApi<SeasonDetail>(enc && `/seasons/${enc}`);
  const days = useApi<Paged<MatchDay>>(enc && `/match-days?season=${enc}&page_size=100`);
  const played = playedNewestFirst(days.data ? rows(days.data) : []);
  const overall = dayId === "overall";
  const day = overall ? null : (played.find((d) => d.id === dayId) ?? played[0] ?? null);
  const table = useApi<Standings>(
    enc && (overall ? `/seasons/${enc}/standings` : day && `/seasons/${enc}/standings?match_day=${day.id}`),
  );
  // Overall only: the latest day's table, to show how far each team moved on it.
  const latest = played[0] ?? null;
  const latestTable = useApi<Standings>(enc && overall && latest ? `/seasons/${enc}/standings?match_day=${latest.id}` : null);
  // Protection Points this period, shown as a column.
  const ppTable = useApi<PPTable>("/pp");
  const pp = useMemo(() => (ppTable.data?.rows.length ? new Map(ppTable.data.rows.map((r) => [r.team.id, r.pp])) : undefined), [ppTable.data]);
  const movement = useMemo(
    () => (overall && table.data && latestTable.data ? overallMovement(table.data.rows, latestTable.data.rows) : undefined),
    [overall, table.data, latestTable.data],
  );

  if (!seasons.data) return <Loading error={seasons.error} count={8} />;
  if (!slug) return <EmptyState title="No season yet">The first season hasn&apos;t started yet.</EmptyState>;
  if (!days.data) return <Loading error={days.error} count={8} />;

  return (
    <>
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        {played.length > 0 && (
          <Tabs
            label="Table"
            tabs={[
              { key: "day", label: "Match day" },
              { key: "overall", label: "Overall" },
            ]}
            value={overall ? "overall" : "day"}
            onChange={(k) => setDayId(k === "overall" ? "overall" : null)}
          />
        )}
        {all.length > 1 && (
          <select
            aria-label="Season"
            className="input sm:w-56"
            value={slug}
            onChange={(e) => {
              setPicked(e.target.value);
              setDayId(null);
            }}
          >
            {all.map((s) => (
              <option key={s.slug} value={s.slug}>
                {s.name}
              </option>
            ))}
          </select>
        )}
        {played.length > 0 && !overall && (
          <select
            aria-label="Match day"
            className="input sm:w-72"
            value={day?.id ?? ""}
            onChange={(e) => setDayId(Number(e.target.value))}
          >
            {played.map((d, i) => (
              <option key={d.id} value={d.id}>
                {dayName(d)}
                {d.date ? ` · ${shortDate(d.date)}` : ""}
                {i === 0 ? " (latest)" : ""}
              </option>
            ))}
          </select>
        )}
      </div>

      {!day && !overall ? (
        <div className="mt-6">
          <EmptyState title="No matches played yet">The table fills in after the first match day is uploaded.</EmptyState>
        </div>
      ) : (
        <>
          <div className="mt-6 flex flex-wrap items-baseline gap-x-3">
            <h2 className="section-title">{day ? dayName(day) : "Overall"}</h2>
            {day?.date && <span className="text-sm text-muted">{shortDate(day.date)}</span>}
            {overall && <span className="text-sm text-muted">{plural(played.length, "match day")} added up</span>}
            {movement && latest && <span className="text-sm text-muted">Arrows: places moved on {dayName(latest)}</span>}
          </div>
          <div className="mt-4">{table.data ? <StandingsTable rows={table.data.rows} movement={movement} pp={pp} /> : <Loading error={table.error} count={8} />}</div>
        </>
      )}
      {detail.data?.scoring && (
        <p className="mt-3 text-xs text-muted">
          Points: {detail.data.scoring.name}, {detail.data.scoring.points_per_kill} per kill.
          {pp && ppTable.data?.period && <> PP: Protection Points for {ppTable.data.period.name}, not part of the total.</>}
        </p>
      )}
    </>
  );
}
