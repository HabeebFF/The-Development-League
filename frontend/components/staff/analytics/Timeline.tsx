"use client";

import Link from "next/link";

import Loading from "@/components/league/Loading";
import { clock, dayLabel, deviceLine, duration, type Timeline as TimelineData } from "@/lib/analytics";
import { useApi } from "@/lib/useApi";

/** One person's day: every page in order, how long they stayed, and what they did there. */
export default function Timeline({ person, date, onBack }: { person: string; date: string; onBack: () => void }) {
  const { data, error } = useApi<TimelineData>(`/analytics/timeline?person=${encodeURIComponent(person)}&date=${date}`);
  return (
    <div className="card p-4 sm:p-5">
      <button type="button" className="text-xs text-muted hover:text-white" onClick={onBack}>
        ← Back
      </button>
      {!data && <div className="mt-3">{<Loading error={error} count={4} />}</div>}
      {data && (
        <>
          <h2 className="mt-2 font-display text-3xl uppercase">{data.person.name}</h2>
          <p className="text-sm text-muted">
            {data.person.team && <span className="text-white">{data.person.team} · </span>}
            {data.person.staff ? "Staff · " : data.person.signed_in ? "Signed in · " : "Not signed in · "}
            {deviceLine(data.person)} · {dayLabel(data.date)}
          </p>
          <ol className="mt-5 space-y-6">
            {data.visits.map((visit, vi) => (
              <li key={visit.start}>
                <p className="eyebrow">
                  Visit {vi + 1} · {clock(visit.start)} · {duration(visit.seconds)}
                </p>
                <ol className="mt-2 border-l border-line">
                  {visit.pages.map((page) => (
                    <li key={page.at} className="relative py-2 pl-5">
                      <span className="absolute top-3.5 -left-[5px] h-2.5 w-2.5 rounded-full bg-accent" aria-hidden />
                      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-sm">
                        <span className="w-11 shrink-0 text-xs text-muted tabular-nums">{clock(page.at)}</span>
                        <Link href={page.path} className="font-semibold hover:text-accent">
                          Opened {page.name}
                        </Link>
                        <span className="text-xs text-muted">{page.seconds == null ? "time not known" : `stayed ${duration(page.seconds)}`}</span>
                        {page.source && <span className="chip">from {page.source}</span>}
                      </div>
                      {page.actions.length > 0 && (
                        <ul className="mt-1.5 space-y-1 pl-14">
                          {page.actions.map((a, i) => (
                            <li key={i} className="flex flex-wrap gap-x-3 text-sm">
                              <span className="w-11 shrink-0 text-xs text-muted tabular-nums">{clock(a.at)}</span>
                              <span>{a.name}</span>
                              {a.detail && <span className="text-xs text-muted">{a.detail}</span>}
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  ))}
                </ol>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}
