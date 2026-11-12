"use client";

import Link from "next/link";
import { useState } from "react";

import EmptyState from "@/components/ui/EmptyState";
import MatchCard, { mapArt } from "@/components/ui/MatchCard";
import Tabs from "@/components/ui/Tabs";
import type { MatchDay, MatchSummary, Paged } from "@/lib/api";
import { currentSeason, dayName, mapName, playedNewestFirst, rows, shortDate, type Season } from "@/lib/league";
import { groupResults, resultMaps, resultWeeks } from "@/lib/results";
import { useApi } from "@/lib/useApi";

import Loading from "./Loading";

/** A match that hasn't been played yet: its map and start time, not a link. */
function Upcoming({ m }: { m: MatchSummary }) {
  const art = mapArt(m.map);
  return (
    <div className="card relative overflow-hidden p-3.5 opacity-70">
      {art && <span aria-hidden className="absolute inset-0 bg-cover bg-center opacity-15 grayscale" style={{ backgroundImage: `url(${art})` }} />}
      <span className="relative block font-display text-xl font-black uppercase">{m.map ? mapName(m.map) : `Match ${m.number}`}</span>
      <span className="relative block text-xs text-muted">
        M{m.number} ·{" "}
        {m.scheduled_at ? new Date(m.scheduled_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "Not played yet"}
      </span>
    </div>
  );
}

/** The current season's played match days, newest first, grouped by date, with week and map filters. */
export default function ResultsView() {
  const seasons = useApi<Paged<Season>>("/seasons?page_size=100");
  const season = seasons.data ? currentSeason(rows(seasons.data)) : null;
  const days = useApi<Paged<MatchDay>>(season && `/match-days?season=${encodeURIComponent(season.slug)}&page_size=100`);
  const [week, setWeek] = useState<number | null>(null);
  const [map, setMap] = useState<string>("all");

  if (seasons.data && !season) return <EmptyState title="No season yet">The first season hasn&apos;t started yet.</EmptyState>;
  if (!days.data) return <Loading error={seasons.error ?? days.error} count={6} />;
  const played = playedNewestFirst(rows(days.data));
  if (!played.length) return <EmptyState title="No matches played yet">Results show up here after the first match day is uploaded.</EmptyState>;

  const startsOn = season?.starts_on ?? null;
  const weeks = resultWeeks(played, startsOn);
  const maps = resultMaps(played);
  const groups = groupResults(played, { startsOn, week, map: map === "all" ? null : map });

  return (
    <>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="-mx-4 min-w-0 overflow-x-auto px-4 pb-1 lg:mx-0 lg:flex-1 lg:px-0">
          <Tabs
            label="Map"
            tabs={[{ key: "all", label: "All maps" }, ...maps.map((m) => ({ key: m, label: mapName(m) }))]}
            value={map}
            onChange={setMap}
          />
        </div>
        {weeks.length > 1 && (
          <select
            aria-label="Week"
            className="input shrink-0 lg:!w-56"
            value={week ?? ""}
            onChange={(e) => setWeek(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">All weeks</option>
            {weeks.map((w) => (
              <option key={w} value={w}>
                Week {w}
              </option>
            ))}
          </select>
        )}
      </div>

      {!groups.length ? (
        <div className="mt-8">
          <EmptyState title="No matches here">Nothing was played on {map === "all" ? "these filters" : mapName(map)}{week ? ` in week ${week}` : ""}.</EmptyState>
        </div>
      ) : (
        <div className="mt-8 space-y-12">
          {groups.map((g) => (
            <section key={g.date ?? "undated"} aria-label={g.date ? shortDate(g.date) : "Undated"}>
              <div className="flex items-baseline gap-3 border-b border-line pb-2">
                <h2 className="font-display text-3xl leading-none font-black uppercase">{g.date ? shortDate(g.date) : "Undated"}</h2>
                {g.week != null && <span className="chip chip-gold">Week {g.week}</span>}
              </div>
              <div className="mt-5 space-y-8">
                {g.days.map(({ day, matches }) => {
                  const meta = [day.stage, day.group].filter(Boolean).join(" · ");
                  return (
                    <div key={day.id}>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="min-w-0">
                          <h3 className="section-title">{dayName(day)}</h3>
                          {meta && <p className="mt-1 text-xs text-muted">{meta}</p>}
                        </div>
                        <Link href={`/results/${day.id}`} className="btn btn-ghost">
                          Day table &rsaquo;
                        </Link>
                      </div>
                      <ul className="stagger mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
                        {matches.map((m) => (
                          <li key={m.id}>
                            {m.played ? (
                              <MatchCard href={`/matches/${m.id}`} map={m.map} label={`M${m.number}`} booyah={m.booyah?.name} />
                            ) : (
                              <Upcoming m={m} />
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}
    </>
  );
}
