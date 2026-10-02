import Link from "next/link";

import type { MatchDay } from "@/lib/api";
import { dayName, mapName, shortDate } from "@/lib/league";

/** One match day: its matches with map and Booyah team, linking to each match. */
export default function MatchDayCard({ day, link = true }: { day: MatchDay; link?: boolean }) {
  const meta = [day.stage, day.group, shortDate(day.date)].filter(Boolean).join(" · ");
  const title = (
    <>
      <span className="block font-display text-2xl leading-tight uppercase">{dayName(day)}</span>
      {meta && <span className="block text-xs text-muted">{meta}</span>}
    </>
  );
  return (
    <div className="card card-hover">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
        {link ? (
          <Link href={`/results/${day.id}`} className="min-w-0 transition-colors hover:text-accent">
            {title}
          </Link>
        ) : (
          <div className="min-w-0">{title}</div>
        )}
        {link && (
          <Link href={`/results/${day.id}`} className="chip shrink-0 transition-colors hover:border-accent hover:text-accent">
            Day table
          </Link>
        )}
      </div>
      <ul className="divide-y divide-line">
        {day.matches.map((m) => (
          <li key={m.id}>
            {m.played ? (
              <Link href={`/matches/${m.id}`} className="group flex items-center gap-3 px-4 py-3 text-sm transition-colors hover:bg-white/[0.03]">
                <span className="w-9 shrink-0 font-display text-lg text-muted group-hover:text-accent">M{m.number}</span>
                <span className="w-20 shrink-0 text-xs font-semibold tracking-wide text-muted uppercase">{mapName(m.map)}</span>
                <span className="min-w-0 flex-1 truncate text-right">
                  {m.booyah ? (
                    <>
                      <span className="mr-2 font-display text-accent-2 uppercase">Booyah</span>
                      <span className="font-semibold">{m.booyah.name}</span>
                    </>
                  ) : (
                    <span className="text-muted">Played</span>
                  )}
                </span>
                <span className="text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-accent">&rsaquo;</span>
              </Link>
            ) : (
              <span className="flex items-center gap-3 px-4 py-3 text-sm text-muted">
                <span className="w-9 shrink-0 font-display text-lg">M{m.number}</span>
                <span className="w-20 shrink-0 text-xs font-semibold tracking-wide uppercase">{m.map ? mapName(m.map) : ""}</span>
                <span className="flex-1 text-right">
                  {m.scheduled_at ? new Date(m.scheduled_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "Not played yet"}
                </span>
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
