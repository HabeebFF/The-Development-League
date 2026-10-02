"use client";

import Link from "next/link";

import type { MatchDay, Paged } from "@/lib/api";
import { currentSeason, dayName, latestPlayed, rows, type Season, type Standings } from "@/lib/league";
import { useApi } from "@/lib/useApi";

import MatchDayCard from "./MatchDayCard";
import StandingsTable from "./StandingsTable";

/** The front page: the current season's top teams, latest results and next fixtures. */
export default function HomeView() {
  const seasons = useApi<Paged<Season>>("/seasons?page_size=100");
  const season = seasons.data ? currentSeason(rows(seasons.data)) : null;
  const slug = season ? encodeURIComponent(season.slug) : null;
  const days = useApi<Paged<MatchDay>>(slug && `/match-days?season=${slug}&page_size=100`);
  const upcoming = useApi<Paged<MatchDay>>(slug && `/seasons/${slug}/fixtures?upcoming=true&page_size=3`);

  const latest = days.data ? latestPlayed(rows(days.data)) : null;
  // The latest match day's table (the season table only before anything is played).
  const standings = useApi<Standings>(
    slug && (days.data || days.error)
      ? `/seasons/${slug}/standings${latest ? `?match_day=${latest.id}` : ""}`
      : null,
  );
  const next = upcoming.data ? rows(upcoming.data).filter((d) => d.id !== latest?.id) : [];

  return (
    <>
      <section className="mx-auto max-w-6xl px-4 pt-12 pb-8 sm:pt-20">
        <p className="text-sm font-semibold tracking-[0.2em] text-accent uppercase">Free Fire esports</p>
        <h1 className="mt-3 font-display text-5xl leading-none uppercase sm:text-7xl">The Development League</h1>
        <p className="mt-4 max-w-xl text-muted">
          {season ? `${season.name}: standings, results and every team in the league.` : "Standings, results and every team in the league."}
        </p>
      </section>

      <section className="mx-auto max-w-6xl px-4 pb-16">
        {seasons.data && !season && <p className="text-muted">The first season hasn&apos;t started yet.</p>}
        {seasons.error && <p className="text-bad">{seasons.error}</p>}
        {season && (
          <div className="grid gap-8 lg:grid-cols-[3fr_2fr] [&>*]:min-w-0">
            <div>
              <div className="flex items-baseline justify-between">
                <h2 className="font-display text-2xl uppercase">
                  Standings{latest ? <span className="text-muted"> · {dayName(latest)}</span> : null}
                </h2>
                <Link href="/standings" className="text-sm text-accent">
                  Full table &rarr;
                </Link>
              </div>
              <div className="mt-3">
                {standings.data ? (
                  <StandingsTable rows={standings.data.rows.slice(0, 5)} compact />
                ) : (
                  <p className={standings.error ? "text-bad" : "text-muted"}>{standings.error ?? "Loading..."}</p>
                )}
              </div>
            </div>

            <div className="space-y-8">
              <div>
                <div className="flex items-baseline justify-between">
                  <h2 className="font-display text-2xl uppercase">Latest results</h2>
                  <Link href="/results" className="text-sm text-accent">
                    All results &rarr;
                  </Link>
                </div>
                <div className="mt-3">
                  {latest ? (
                    <MatchDayCard day={latest} />
                  ) : (
                    <p className="text-sm text-muted">{days.loading ? "Loading..." : "No matches played yet."}</p>
                  )}
                </div>
              </div>
              {next.length > 0 && (
                <div>
                  <h2 className="font-display text-2xl uppercase">Coming up</h2>
                  <div className="mt-3 space-y-4">
                    {next.map((d) => (
                      <MatchDayCard key={d.id} day={d} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </section>
    </>
  );
}
