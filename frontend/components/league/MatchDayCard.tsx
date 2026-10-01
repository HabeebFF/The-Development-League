import Link from "next/link";

import type { MatchDay } from "@/lib/api";
import { dayName, mapName, shortDate } from "@/lib/league";

/** One match day: its matches with map and Booyah team, linking to each match. */
export default function MatchDayCard({ day, link = true }: { day: MatchDay; link?: boolean }) {
  const title = (
    <>
      {dayName(day)}
      <span className="ml-2 text-xs font-normal text-muted normal-case">
        {[day.stage, day.group, shortDate(day.date)].filter(Boolean).join(" · ")}
      </span>
    </>
  );
  return (
    <div className="rounded-lg border border-line bg-panel">
      <h3 className="border-b border-line px-4 py-3 font-display text-lg uppercase">
        {link ? (
          <Link href={`/results/${day.id}`} className="hover:text-accent">
            {title}
          </Link>
        ) : (
          title
        )}
      </h3>
      <ul className="divide-y divide-line">
        {day.matches.map((m) => (
          <li key={m.id}>
            {m.played ? (
              <Link href={`/matches/${m.id}`} className="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-panel-2">
                <span className="w-16 shrink-0 font-medium">Match {m.number}</span>
                <span className="w-20 shrink-0 text-muted">{mapName(m.map)}</span>
                <span className="min-w-0 flex-1 truncate text-right">
                  {m.booyah ? (
                    <>
                      <span className="text-accent-2">Booyah</span> {m.booyah.name}
                    </>
                  ) : (
                    <span className="text-muted">Played</span>
                  )}
                </span>
              </Link>
            ) : (
              <span className="flex items-center gap-3 px-4 py-2.5 text-sm text-muted">
                <span className="w-16 shrink-0">Match {m.number}</span>
                <span className="w-20 shrink-0">{m.map ? mapName(m.map) : ""}</span>
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
