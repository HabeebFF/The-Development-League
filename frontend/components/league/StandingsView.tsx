"use client";

import { useState } from "react";

import type { MatchDay, Paged } from "@/lib/api";
import { currentSeason, dayName, playedNewestFirst, plural, rows, shortDate, type Season, type SeasonDetail, type Standings } from "@/lib/league";
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

  if (!seasons.data) return <Loading error={seasons.error} count={8} />;
  if (!slug) return <p className="text-muted">The first season hasn&apos;t started yet.</p>;
  if (!days.data) return <Loading error={days.error} count={8} />;

  return (
    <>
      <div className="flex flex-col gap-2 sm:flex-row">
        {all.length > 1 && (
          <select
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
        {played.length > 0 && (
          <select
            className="input sm:w-72"
            value={overall ? "overall" : (day?.id ?? "")}
            onChange={(e) => setDayId(e.target.value === "overall" ? "overall" : Number(e.target.value))}
          >
            {played.map((d, i) => (
              <option key={d.id} value={d.id}>
                {dayName(d)}
                {d.date ? ` · ${shortDate(d.date)}` : ""}
                {i === 0 ? " (latest)" : ""}
              </option>
            ))}
            <option value="overall">Overall (all match days added up)</option>
          </select>
        )}
      </div>

      {!day && !overall ? (
        <p className="mt-4 text-muted">No matches played yet.</p>
      ) : (
        <>
          <div className="mt-6 flex flex-wrap items-baseline gap-x-3">
            <h2 className="section-title">{day ? dayName(day) : "Overall"}</h2>
            {day?.date && <span className="text-sm text-muted">{shortDate(day.date)}</span>}
            {overall && <span className="text-sm text-muted">{plural(played.length, "match day")} added up</span>}
          </div>
          <div className="mt-4">{table.data ? <StandingsTable rows={table.data.rows} /> : <Loading error={table.error} count={8} />}</div>
        </>
      )}
      {detail.data?.scoring && (
        <p className="mt-3 text-xs text-muted">
          Points: {detail.data.scoring.name}, {detail.data.scoring.points_per_kill} per kill.
        </p>
      )}
    </>
  );
}
