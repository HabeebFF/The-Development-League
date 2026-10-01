"use client";

import Link from "next/link";

import { dayName, shortDate, type MatchDayDetail } from "@/lib/league";
import { useApi } from "@/lib/useApi";

import Loading from "./Loading";
import MatchDayCard from "./MatchDayCard";
import StandingsTable from "./StandingsTable";

/** One match day: its table and its matches. */
export default function MatchDayView({ id }: { id: number }) {
  const day = useApi<MatchDayDetail>(`/match-days/${id}`);
  if (!day.data) return <Loading error={day.error} />;
  const d = day.data;
  return (
    <>
      <Link href="/results" className="text-sm text-muted hover:text-text">
        &larr; Results
      </Link>
      <h1 className="mt-2 font-display text-4xl uppercase">{dayName(d)}</h1>
      <p className="mt-1 text-sm text-muted">{[d.stage, d.group, shortDate(d.date)].filter(Boolean).join(" · ")}</p>
      <div className="mt-6 grid gap-8 lg:grid-cols-[3fr_2fr] [&>*]:min-w-0">
        <div>
          <h2 className="font-display text-2xl uppercase">Day table</h2>
          <div className="mt-3">
            <StandingsTable rows={d.standings} />
          </div>
        </div>
        <div>
          <h2 className="font-display text-2xl uppercase">Matches</h2>
          <div className="mt-3">
            <MatchDayCard day={d} link={false} />
          </div>
        </div>
      </div>
    </>
  );
}
