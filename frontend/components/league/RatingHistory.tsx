"use client";

import Link from "next/link";

import { shortDate } from "@/lib/league";
import { BAND_CLASSES, matchCount, ratingText, type PlayerRatings } from "@/lib/ratings";
import { useApi } from "@/lib/useApi";

import RatingBadge from "./RatingBadge";

const DAYS = 10; // daily ratings shown

/** A player's rating out of 10: their last 7 and 30 days, and their last few match days. */
export default function RatingHistory({ id }: { id: string }) {
  const data = useApi<PlayerRatings>(`/ratings/player/${id}`);
  const r = data.data;
  if (!r || !r.days.length) return null;
  const days = r.days.slice(-DAYS);
  const summary = [
    { label: "Last 7 days", v: r.week },
    { label: "Last 30 days", v: r.month },
  ];
  return (
    <section className="mt-12">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="section-title">Match ratings</h2>
        <Link href="/ratings" className="text-sm text-accent hover:underline">
          All ratings &rarr;
        </Link>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {summary.map((s) => (
          <div key={s.label} className="card flex items-center justify-between gap-3 p-4">
            <span>
              <span className="block text-xs font-bold tracking-widest text-muted uppercase">{s.label}</span>
              <span className="block text-xs text-muted">{s.v ? matchCount(s.v.matches) : "No matches"}</span>
            </span>
            {s.v ? <RatingBadge rating={s.v.rating} band={s.v.band} /> : <span className="text-muted">–</span>}
          </div>
        ))}
        {r.all && (
          <div className="card col-span-2 flex items-center justify-between gap-3 p-4 sm:col-span-1">
            <span>
              <span className="block text-xs font-bold tracking-widest text-muted uppercase">All time</span>
              <span className="block text-xs text-muted">{matchCount(r.all.matches)}</span>
            </span>
            <span className="font-display text-2xl">{ratingText(r.all.rating)}</span>
          </div>
        )}
      </div>
      <h3 className="mt-6 font-display text-xl uppercase">Day by day</h3>
      <div className="mt-3 flex h-44 items-end gap-1.5 sm:gap-2" role="img" aria-label={`Daily ratings, latest ${ratingText(days[days.length - 1].rating)}`}>
        {days.map((d) => (
          <div key={d.date} className="flex h-full min-w-0 max-w-16 flex-1 flex-col items-center justify-end gap-1" title={`${shortDate(d.date)}: ${ratingText(d.rating)} from ${matchCount(d.matches)}`}>
            <span className="text-xs font-bold tabular-nums">{ratingText(d.rating)}</span>
            <span className={`w-full max-w-10 rounded-t-sm ${BAND_CLASSES[d.band]}`} style={{ height: `${Math.max(6, ((d.rating - 3) / 7) * 100)}%` }} />
            <span className="w-full truncate text-center text-[10px] text-muted">{dayMonth(d.date)}</span>
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs text-muted">A day&apos;s rating is the average of the player&apos;s matches that day (8PM and 10PM together).</p>
    </section>
  );
}

function dayMonth(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}
