"use client";

import Link from "next/link";

import type { MatchDay, Paged } from "@/lib/api";
import { currentSeason, dayName, playedNewestFirst, rows, shortDate, type Season, type Standings, type StandingRow } from "@/lib/league";
import { periodLabel, type Awards } from "@/lib/awards";
import { podiumOrder, seasonWeek } from "@/lib/home";
import { killsLabel, killsPath, type KillList } from "@/lib/kills";
import { GROUPS, PLAYER_PAGES, TEAM_PAGES } from "@/lib/nav";
import type { DayRatings } from "@/lib/ratings";
import { useApi } from "@/lib/useApi";
import { useCountUp } from "@/lib/useCountUp";
import EmptyState from "@/components/ui/EmptyState";
import LionMark from "@/components/ui/LionMark";
import MatchCard from "@/components/ui/MatchCard";
import PlayerAvatar from "@/components/ui/PlayerAvatar";
import SectionHeader from "@/components/ui/SectionHeader";
import TrophyCard from "@/components/ui/TrophyCard";

import CardCountdown from "./CardCountdown";
import ExploreGrid from "./ExploreGrid";
import { Skeleton, SkeletonRows } from "./Loading";
import MatchDayCard from "./MatchDayCard";
import WeekStars from "./WeekStars";
import RatingBadge from "./RatingBadge";
import { TeamMark } from "./TeamBadge";

/** A top-three team on the podium: big place number, crest, name and points. 1st stands tallest. */
function PodiumCard({ row }: { row: StandingRow }) {
  const first = row.rank === 1;
  const metal = row.rank === 1 ? "from-[var(--gold-hi)] to-[var(--gold)]" : row.rank === 2 ? "from-[var(--silver-hi)] to-[var(--silver)]" : "from-[var(--bronze-hi)] to-[var(--bronze)]";
  return (
    <Link
      href={`/teams/${row.team.slug}`}
      className={`card card-hover flex flex-col items-center gap-2 px-3 pb-5 text-center ${
        first ? "order-first col-span-2 pt-7 sm:order-none sm:col-span-1 bg-[radial-gradient(90%_60%_at_50%_0%,rgb(255_224_138/0.18),transparent_70%)]" : "pt-5 sm:mt-8"
      }`}
    >
      <span className={`num bg-gradient-to-b ${metal} bg-clip-text leading-[0.8] text-transparent ${first ? "text-8xl" : "text-6xl"}`}>{row.rank}</span>
      <TeamMark team={row.team} size="lg" />
      <span className="w-full truncate font-display text-xl leading-tight font-extrabold uppercase">{row.team.name}</span>
      <span className="num text-3xl leading-none">
        <Count value={row.total_points} />
        <span className="ml-1 text-sm tracking-[0.14em] text-muted">PTS</span>
      </span>
      <span className="text-xs text-muted">
        <span className={row.booyahs ? "text-accent-2" : ""}>
          {row.booyahs} Booyah{row.booyahs === 1 ? "" : "s"}
        </span>{" "}
        · {row.kills} kills
      </span>
      <span className={`mt-1 h-1 w-full bg-gradient-to-r ${metal} ${first ? "shadow-[0_0_18px_var(--gold)]" : ""}`} aria-hidden />
    </Link>
  );
}

/** A number that counts up when it scrolls in. */
function Count({ value }: { value: number }) {
  const [ref, shown] = useCountUp(value);
  return <span ref={ref}>{shown}</span>;
}

/** The front page: lion hero, podium, results ticker, top fragger, Saturday's cards and the week's awards. */
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
  const recent = played
    .flatMap((d) => d.matches.filter((m) => m.played).map((m) => ({ ...m, day: d })))
    .sort((a, b) => (b.started_at ?? "").localeCompare(a.started_at ?? ""));
  const replays = recent.slice(0, 4);
  const ticker = recent.slice(0, 10);
  const loadingDays = !!season && !days.data && !days.error;
  const matchesPlayed = played.reduce((n, d) => n + d.matches.filter((m) => m.played).length, 0);
  const week = season && latest ? seasonWeek(season.starts_on, latest.date) : null;
  const podium = standings.data ? podiumOrder(standings.data.rows) : [];

  return (
    <>
      <section className="relative overflow-hidden border-b border-line">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(50rem_26rem_at_78%_30%,rgb(245_165_36/0.22),transparent_60%),radial-gradient(30rem_20rem_at_10%_90%,rgb(255_46_77/0.1),transparent_60%)]" />
        <div className="hex-grid pointer-events-none absolute inset-0 opacity-40" />
        <LionMark className="pointer-events-none absolute top-1/2 -right-16 h-[22rem] w-[22rem] -translate-y-1/2 opacity-[0.13] sm:right-0 sm:h-[34rem] sm:w-[34rem]" />
        <div className="stagger relative mx-auto max-w-6xl px-4 pt-10 pb-10 sm:pt-16 sm:pb-14">
          <p className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span className="eyebrow">{[season?.name ?? "Free Fire esports", week ? `Week ${week}` : null].filter(Boolean).join(" · ")}</span>
            {latest && <span className="chip chip-hot">Latest: {dayName(latest)}</span>}
          </p>
          <h1 className="mt-3 font-display text-[clamp(3.25rem,13vw,7.5rem)] leading-[0.86] font-black tracking-[-0.01em] uppercase">
            The Development
            <br />
            <span className="text-lion-gradient">League</span>
          </h1>
          <p className="mt-4 max-w-xl text-muted sm:mt-5 sm:text-lg">
            Free Fire&apos;s proving ground. 8PM and 10PM scrims, the full table, every result, each player&apos;s kills and rating, and
            every match again as a 2D replay.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Link href="/standings" className="btn btn-primary px-6 text-base">
              View standings <span aria-hidden>&rarr;</span>
            </Link>
            <Link href={latest ? `/results/${latest.id}` : "/results"} className="btn px-6 text-base">
              Latest results
            </Link>
          </div>
          {latest && (
            <dl className="mt-9 grid max-w-lg grid-cols-3 gap-4">
              {(
                [
                  ["Matches", matchesPlayed],
                  ["Match days", played.length],
                  ["Teams", standings.data?.rows.length ?? null],
                ] as [string, number | null][]
              ).map(([label, value]) => (
                <div key={label} className="border-l-2 border-accent/60 pl-3">
                  <dt className="text-[10px] font-bold tracking-[0.2em] text-muted uppercase">{label}</dt>
                  <dd className="num text-3xl sm:text-4xl">{value == null ? "–" : <Count value={value} />}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </section>

      <div className="mx-auto max-w-6xl space-y-14 px-4 py-10 sm:py-14">
        {seasons.error && <p className="text-bad">{seasons.error}</p>}
        {seasons.data && !season && (
          <EmptyState title="Season loading up">The first season hasn&apos;t started yet. The table and results appear here once it does.</EmptyState>
        )}
        {!seasons.data && !seasons.error && <SkeletonRows count={4} className="h-16" />}

        {season && (
          <section>
            <SectionHeader title="Top of the table" href="/standings" link="Full standings" />
            {latest && (
              <p className="-mt-2 mb-4 text-sm text-muted">
                {dayName(latest)}
                {latest.date ? ` · ${shortDate(latest.date)}` : ""}
              </p>
            )}
            {days.data && !latest ? (
              <EmptyState title="No matches yet">The podium fills in after the first match day is uploaded.</EmptyState>
            ) : podium.length ? (
              <div className="stagger grid grid-cols-2 items-start gap-3 sm:grid-cols-3">
                {podium.map((r) => (
                  <PodiumCard key={r.team.id} row={r} />
                ))}
              </div>
            ) : standings.error ? (
              <p className="text-bad">{standings.error}</p>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <Skeleton className="col-span-2 h-60 sm:col-span-1" />
                <Skeleton className="h-52" />
                <Skeleton className="h-52" />
              </div>
            )}
          </section>
        )}

        {season && (
          <section>
            <SectionHeader title="Latest results" href="/results" link="All results" />
            {ticker.length ? (
              <div className="-mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-2 [scrollbar-color:var(--line)_transparent] [scrollbar-width:thin]">
                {ticker.map((m) => (
                  <MatchCard
                    key={m.id}
                    href={`/matches/${m.id}`}
                    map={m.map}
                    label={`${dayName(m.day)} · M${m.number}`}
                    booyah={m.booyah?.name}
                    className="w-[78vw] max-w-[300px] shrink-0 snap-start sm:w-[280px]"
                  />
                ))}
              </div>
            ) : loadingDays ? (
              <div className="flex gap-3 overflow-hidden">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-40 w-[280px] shrink-0" />
                ))}
              </div>
            ) : (
              <EmptyState title="No results yet">Match cards appear here as soon as staff upload tonight&apos;s logs.</EmptyState>
            )}
          </section>
        )}

        {season && <Stars />}

        <section>
          <SectionHeader title="New cards every Saturday" href="/cards" link="All player cards" />
          <CardCountdown />
          <WeekStars />
        </section>

        {season && <WeekAwards />}

        {next.length > 0 && (
          <section>
            <SectionHeader title="Upcoming fixtures" />
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {next.map((d) => (
                <MatchDayCard key={d.id} day={d} link={false} />
              ))}
            </div>
          </section>
        )}

        {replays.length > 0 && (
          <section>
            <SectionHeader title="Watch replays" href={`/matches/${replays[0].id}/replay`} link="Latest 2D replay" />
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {replays.map((m) => (
                <MatchCard
                  key={m.id}
                  href={m.vod_url || `/matches/${m.id}/replay`}
                  map={m.map}
                  label={`M${m.number}`}
                  booyah={m.booyah?.name}
                  footer={m.vod_url ? "Watch video" : "2D replay"}
                />
              ))}
            </div>
          </section>
        )}

        <section>
          <SectionHeader title="Explore the league" />
          <ExploreGrid links={EXPLORE} />
        </section>
      </div>
    </>
  );
}

// Every page, in the order a new visitor needs them.
const EXPLORE = [GROUPS[0], GROUPS[1], ...PLAYER_PAGES, { ...TEAM_PAGES[0], label: "Teams" }, TEAM_PAGES[1]];

/** Spotlight: this week's top fragger, and the latest day's best-rated player. */
function Stars() {
  const kills = useApi<KillList>(killsPath("week", null));
  const ratings = useApi<DayRatings>("/ratings");
  const top = kills.data?.players[0];
  const star = ratings.data?.players.find((p) => p.player_id === ratings.data?.star);
  if (!kills.data && !ratings.data) return null;
  if (!(top && top.kills > 0) && !star) return null;
  return (
    <section>
      <SectionHeader title="Top fragger this week" href="/kills" link="Kill list" />
      <div className="grid gap-3 lg:grid-cols-[3fr_2fr]">
        {top && top.kills > 0 ? (
          <Link
            href="/kills"
            className="card card-hover grid grid-cols-[auto_1fr] items-center gap-5 overflow-hidden bg-[radial-gradient(80%_120%_at_0%_50%,rgb(255_46_77/0.16),transparent_70%)] p-5"
          >
            <PlayerAvatar name={top.player} colour={top.team?.primary_color} size="xl" />
            <span className="min-w-0">
              <span className="chip chip-hot">{kills.data ? killsLabel(kills.data) : "This week"}</span>
              <span className="num mt-2 block text-7xl leading-[0.85] sm:text-8xl">
                <Count value={top.kills} />
                <span className="ml-2 text-xl tracking-[0.12em] text-hot">KILLS</span>
              </span>
              <span className="mt-2 block truncate font-display text-3xl font-black uppercase">{top.player}</span>
              <span className="mt-1 flex items-center gap-2 text-sm text-muted">
                {top.team && <TeamMark team={top.team} />}
                <span className="truncate">
                  {[top.team?.name, `${top.matches} ${top.matches === 1 ? "match" : "matches"}`, top.hs_pct != null ? `${Math.round(top.hs_pct)}% HS` : null]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </span>
            </span>
          </Link>
        ) : (
          <EmptyState title="No kills yet this week">The first scrim of the week puts someone here.</EmptyState>
        )}
        {star && (
          <Link href="/ratings" className="card card-hover flex items-center gap-4 p-5">
            {star.team && <TeamMark team={star.team} size="md" />}
            <span className="min-w-0 flex-1">
              <span className="eyebrow block">Player of the Day</span>
              <span className="block truncate font-display text-2xl font-black uppercase">{star.player}</span>
              <span className="block truncate text-xs text-muted">{[star.team?.name, ratings.data?.date && shortDate(ratings.data.date)].filter(Boolean).join(" · ")}</span>
            </span>
            <RatingBadge rating={star.rating} band={star.band} size="lg" />
          </Link>
        )}
      </div>
    </section>
  );
}

/** This week's award winners as a trophy case, linking to the Awards page. */
function WeekAwards() {
  const awards = useApi<Awards>("/awards?period=week");
  if (!awards.data || awards.data.matches === 0) return null;
  return (
    <section>
      <SectionHeader title="Awards of the week" href="/awards" link="All awards" />
      <p className="-mt-2 mb-4 text-sm text-muted">{periodLabel(awards.data)}</p>
      <div className="stagger grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {awards.data.awards.map((a) => (
          <TrophyCard key={a.key} award={a} />
        ))}
      </div>
    </section>
  );
}
