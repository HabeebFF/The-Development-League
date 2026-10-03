"use client";

import Link from "next/link";

import type { MatchDay, Paged } from "@/lib/api";
import { currentSeason, dayName, mapName, playedNewestFirst, rows, shortDate, type Season, type Standings, type StandingRow } from "@/lib/league";
import { useApi } from "@/lib/useApi";

import { Skeleton, SkeletonRows } from "./Loading";
import MatchDayCard from "./MatchDayCard";
import { RankBadge } from "./StandingsTable";
import { TeamMark } from "./TeamBadge";

function SectionHead({ title, href, link }: { title: string; href?: string; link?: string }) {
  return (
    <div className="flex items-end justify-between gap-4">
      <h2 className="section-title">{title}</h2>
      {href && (
        <Link href={href} className="shrink-0 text-xs font-bold tracking-widest text-accent uppercase hover:text-accent-hot">
          {link} &rarr;
        </Link>
      )}
    </div>
  );
}

function TopTeam({ row }: { row: StandingRow }) {
  return (
    <Link
      href={`/teams/${row.team.slug}`}
      className={`card card-hover flex items-center gap-3 p-3 ${row.rank === 1 ? "border-gold/40 bg-[linear-gradient(110deg,rgb(246_197_68/0.10),transparent_55%)]" : ""}`}
    >
      <RankBadge rank={row.rank} />
      <TeamMark team={row.team} size="md" />
      <span className="min-w-0 flex-1">
        <span className="block truncate font-display text-xl leading-tight uppercase">{row.team.name}</span>
        <span className="text-xs text-muted">
          <span className={row.booyahs ? "text-accent-2" : ""}>{row.booyahs} Booyah</span> · {row.kills} kills
        </span>
      </span>
      <span className="text-right">
        <span className="block font-display text-3xl leading-none text-white">{row.total_points}</span>
        <span className="text-[10px] font-bold tracking-widest text-muted uppercase">pts</span>
      </span>
    </Link>
  );
}

/** The front page: hero, the latest match day's top five, results, fixtures and replays. */
export default function HomeView() {
  const seasons = useApi<Paged<Season>>("/seasons?page_size=100");
  const season = seasons.data ? currentSeason(rows(seasons.data)) : null;
  const slug = season ? encodeURIComponent(season.slug) : null;
  const days = useApi<Paged<MatchDay>>(slug && `/match-days?season=${slug}&page_size=100`);
  const upcoming = useApi<Paged<MatchDay>>(slug && `/seasons/${slug}/fixtures?upcoming=true&page_size=3`);

  const played = days.data ? playedNewestFirst(rows(days.data)) : [];
  const latest = played[0] ?? null;
  // The headline table is the latest match day's, not the season's running total.
  const standings = useApi<Standings>(slug && latest && `/seasons/${slug}/standings?match_day=${latest.id}`);
  const next = upcoming.data ? rows(upcoming.data).filter((d) => d.id !== latest?.id) : [];
  const replays = played
    .flatMap((d) => d.matches.filter((m) => m.played).map((m) => ({ ...m, day: d })))
    .sort((a, b) => (b.started_at ?? "").localeCompare(a.started_at ?? ""))
    .slice(0, 4);
  const loadingDays = !!season && !days.data && !days.error;
  const matchesPlayed = played.reduce((n, d) => n + d.matches.filter((m) => m.played).length, 0);

  return (
    <>
      <section className="relative overflow-hidden border-b border-line">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(50rem_26rem_at_75%_0%,rgb(255_90_31/0.28),transparent_65%)]" />
        <div className="pointer-events-none absolute -right-24 top-0 h-full w-2/3 -skew-x-[20deg] bg-[repeating-linear-gradient(90deg,rgb(255_255_255/0.03)_0_2px,transparent_2px_18px)]" />
        <div className="pointer-events-none absolute -right-6 -bottom-10 font-display text-[11rem] leading-none text-white/[0.03] select-none sm:text-[18rem]">
          TDL
        </div>
        <div className="relative mx-auto max-w-6xl px-4 pt-12 pb-12 sm:pt-24 sm:pb-20">
          <p className="eyebrow">Free Fire esports{season ? ` · ${season.name}` : ""}</p>
          <h1 className="mt-3 font-display text-6xl leading-[0.9] font-extrabold uppercase sm:text-8xl">
            The Development
            <br />
            <span className="bg-gradient-to-r from-accent to-accent-2 bg-clip-text text-transparent">League</span>
          </h1>
          <p className="mt-5 max-w-lg text-muted sm:text-lg">
            Every Booyah, every kill, every rotation. Follow the standings, results and teams of the league.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href={latest ? `/results/${latest.id}` : "/results"} className="btn btn-primary px-6 py-3 text-base">
              Latest results
            </Link>
            <Link href="/standings" className="btn px-6 py-3 text-base uppercase">
              Standings
            </Link>
          </div>
          {latest && (
            <dl className="mt-10 flex gap-8 sm:gap-12">
              {[
                ["Latest", dayName(latest)],
                ["Matches", String(matchesPlayed)],
                ["Match days", String(played.length)],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt className="text-[10px] font-bold tracking-widest text-muted uppercase">{label}</dt>
                  <dd className="font-display text-2xl uppercase sm:text-3xl">{value}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </section>

      <div className="mx-auto max-w-6xl space-y-14 px-4 py-10 sm:py-14">
        {seasons.error && <p className="text-bad">{seasons.error}</p>}
        {seasons.data && !season && <p className="text-muted">The first season hasn&apos;t started yet.</p>}
        {!seasons.data && !seasons.error && <SkeletonRows count={5} className="h-16" />}

        {season && (
          <div className="grid gap-10 lg:grid-cols-[3fr_2fr] [&>*]:min-w-0">
            <section>
              <SectionHead title="Top 5" href="/standings" link="Full table" />
              {latest && <p className="mt-1 text-sm text-muted">{dayName(latest)}{latest.date ? ` · ${shortDate(latest.date)}` : ""}</p>}
              <div className="mt-4 space-y-2">
                {days.data && !latest ? (
                  <p className="text-sm text-muted">No matches played yet.</p>
                ) : standings.data ? (
                  standings.data.rows.slice(0, 5).map((r) => <TopTeam key={r.team.id} row={r} />)
                ) : standings.error ? (
                  <p className="text-bad">{standings.error}</p>
                ) : (
                  <SkeletonRows count={5} className="h-16" />
                )}
              </div>
            </section>

            <section>
              <SectionHead title="Latest results" href="/results" link="All results" />
              <div className="mt-4">
                {latest ? (
                  <MatchDayCard day={latest} />
                ) : loadingDays ? (
                  <Skeleton className="h-64" />
                ) : (
                  <p className="text-sm text-muted">No matches played yet.</p>
                )}
              </div>
            </section>
          </div>
        )}

        {next.length > 0 && (
          <section>
            <SectionHead title="Upcoming fixtures" />
            <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {next.map((d) => (
                <MatchDayCard key={d.id} day={d} link={false} />
              ))}
            </div>
          </section>
        )}

        {replays.length > 0 && (
          <section>
            <SectionHead title="Watch replays" href={`/matches/${replays[0].id}/replay`} link="Latest 2D replay" />
            <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
              {replays.map((m) => (
                <Link
                  key={m.id}
                  href={m.vod_url || `/matches/${m.id}/replay`}
                  {...(m.vod_url ? { target: "_blank", rel: "noreferrer" } : {})}
                  className="card card-hover group flex aspect-[4/3] flex-col justify-between overflow-hidden p-3 sm:p-4"
                >
                  <span className="pointer-events-none absolute inset-0 bg-[linear-gradient(160deg,rgb(255_90_31/0.18),transparent_55%)] opacity-60 transition-opacity group-hover:opacity-100" />
                  <span className="relative flex items-start justify-between gap-2">
                    <span className="chip">{dayName(m.day)}</span>
                    <span
                      className="flex h-9 w-9 items-center justify-center bg-accent text-white shadow-[0_0_16px_rgb(255_90_31/0.6)] transition-transform group-hover:scale-110"
                      style={{ clipPath: "polygon(0 0, 100% 50%, 0 100%)" }}
                      aria-hidden
                    />
                  </span>
                  <span className="relative">
                    <span className="block font-display text-2xl leading-none uppercase sm:text-3xl">{mapName(m.map)}</span>
                    <span className="mt-1 block truncate text-xs text-muted">
                      Match {m.number}
                      {m.booyah ? ` · Booyah ${m.booyah.name}` : ""}
                    </span>
                    <span className="mt-1 block text-[10px] font-bold tracking-widest text-accent uppercase">
                      {m.vod_url ? "Watch video" : "2D replay"}
                    </span>
                  </span>
                </Link>
              ))}
            </div>
          </section>
        )}
      </div>
    </>
  );
}
