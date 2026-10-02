"use client";

import Link from "next/link";

import { dayName, shortDate, type MatchDayDetail } from "@/lib/league";
import { useApi } from "@/lib/useApi";

import Loading, { Skeleton } from "./Loading";
import MatchDayCard from "./MatchDayCard";
import PageHeader from "./PageHeader";
import StandingsTable from "./StandingsTable";

/** One match day: its table and its matches. */
export default function MatchDayView({ id }: { id: number }) {
  const day = useApi<MatchDayDetail>(`/match-days/${id}`);
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
      </div>
    </>
  );
}
