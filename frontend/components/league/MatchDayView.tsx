"use client";

import Link from "next/link";

import type { KillList } from "@/lib/kills";
import { ratingsPath, type DayRatings } from "@/lib/ratings";
import { dayName, shortDate, type MatchDayDetail } from "@/lib/league";
import { useApi } from "@/lib/useApi";

import KillTable from "./KillTable";
import Loading, { Skeleton } from "./Loading";
import MatchDayCard from "./MatchDayCard";
import PageHeader from "./PageHeader";
import RatingTable, { StarPlayer } from "./RatingTable";
import StandingsTable from "./StandingsTable";

/** One match day (a session): its table, its matches and its kill list. */
export default function MatchDayView({ id }: { id: number }) {
  const day = useApi<MatchDayDetail>(`/match-days/${id}`);
  const kills = useApi<KillList>(`/kills?session=${id}`);
  const ratings = useApi<DayRatings>(ratingsPath(null, id));
  if (!day.data)
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        {day.error ? <Loading error={day.error} /> : <Skeleton className="mb-8 h-24" />}
        {!day.error && <Loading count={8} />}
      </div>
    );
  const d = day.data;
  return (
    <>
      <PageHeader eyebrow="Match day results" title={dayName(d)}>
        {[d.stage, d.group, shortDate(d.date)].filter(Boolean).join(" · ")}
      </PageHeader>
      <div className="mx-auto max-w-6xl px-4 py-8">
        <Link href="/results" className="text-xs font-bold tracking-widest text-muted uppercase hover:text-accent">
          &larr; All results
        </Link>
        <div className="mt-4 grid gap-10 lg:grid-cols-[3fr_2fr] [&>*]:min-w-0">
          <section>
            <h2 className="section-title">Day table</h2>
            <div className="mt-4">
              <StandingsTable rows={d.standings} />
            </div>
          </section>
          <section>
            <h2 className="section-title">Matches</h2>
            <div className="mt-4">
              <MatchDayCard day={d} link={false} />
            </div>
          </section>
        </div>
        {ratings.data && ratings.data.matches > 0 && (
          <section className="mt-10">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="section-title">Top ratings</h2>
              <Link href={`/ratings?session=${id}`} className="text-sm text-accent hover:underline">
                All ratings &rarr;
              </Link>
            </div>
            <div className="mt-4 space-y-4">
              {ratings.data.star != null && (
                <StarPlayer row={ratings.data.players.find((p) => p.player_id === ratings.data!.star)!} label="Player of the session" />
              )}
              <RatingTable board={ratings.data} limit={5} />
            </div>
          </section>
        )}
        <section className="mt-10">
          <h2 className="section-title">Kill list</h2>
          <div className="mt-4">{kills.data ? <KillTable list={kills.data} /> : <Loading error={kills.error} count={6} />}</div>
        </section>
      </div>
    </>
  );
}
