"use client";

import { useState } from "react";

import Loading from "@/components/league/Loading";
import { clock, compact, type DayPerson, type DayReport, dayLabel, deviceLine, duration, leagueToday, shiftDay, type Who } from "@/lib/analytics";
import { useApi } from "@/lib/useApi";

import { HoursChart } from "./Overview";
import { ListCard, Row, Tile } from "./parts";
import Timeline from "./Timeline";

/** One day in full: its numbers, hours, pages, actions and everyone who came. */
export default function DayView({ who, date, onDate, person, onPerson }: { who: Who; date: string; onDate: (d: string) => void; person: string | null; onPerson: (p: string | null) => void }) {
  const { data, error } = useApi<DayReport>(`/analytics/day?date=${date}&who=${who}`);
  const today = leagueToday();
  const [query, setQuery] = useState("");

  if (person) return <Timeline person={person} date={date} onBack={() => onPerson(null)} />;

  const people = (data?.people ?? []).filter((p) => !query || `${p.name} ${p.team} ${p.source}`.toLowerCase().includes(query.toLowerCase()));
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex items-center gap-2">
          <button type="button" className="btn px-3 py-1.5" onClick={() => onDate(shiftDay(date, -1))} aria-label="Day before">
            ←
          </button>
          <input type="date" className="input w-40" value={date} max={today} onChange={(e) => e.target.value && onDate(e.target.value)} aria-label="Day" />
          <button type="button" className="btn px-3 py-1.5" onClick={() => onDate(shiftDay(date, 1))} disabled={date >= today} aria-label="Day after">
            →
          </button>
        </div>
        <span className="font-display text-2xl uppercase">{dayLabel(date)}</span>
      </div>

      {!data && <Loading error={error} count={6} />}
      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Tile label="People" value={compact(data.totals.people)} note={`${data.totals.signed_in} signed in`} />
            <Tile label="Page views" value={compact(data.totals.views)} />
            <Tile label="Actions" value={compact(data.totals.actions)} />
            <Tile label="Time on site" value={duration(data.totals.seconds)} note={`${duration(data.totals.avg_visit_s)} per visit`} />
          </div>
          {data.totals.views === 0 ? (
            <div className="card p-6 text-sm text-muted">Nobody visited on this day.</div>
          ) : (
            <>
              <div className="card p-4 sm:p-5">
                <h2 className="section-title">Everyone who came</h2>
                <p className="mt-1 text-xs text-muted">Tap a name to see everything they did, in order. Visitors without an account get a new code each day.</p>
                <input type="search" className="input mt-3 max-w-xs" placeholder="Find a name, team or source" value={query} onChange={(e) => setQuery(e.target.value)} />
                {/* Phones: one card per person. */}
                <ul className="mt-3 space-y-2 sm:hidden">
                  {people.map((p) => (
                    <li key={p.key}>
                      <button type="button" className="w-full border border-line bg-panel-2 p-3 text-left" onClick={() => onPerson(p.key)}>
                        <span className="flex items-baseline justify-between gap-2">
                          <span className="font-semibold">{p.name}</span>
                          <span className="text-xs text-muted tabular-nums">
                            {clock(p.first)}
                            {p.last !== p.first && `–${clock(p.last)}`}
                          </span>
                        </span>
                        <span className="block text-xs text-muted">
                          {whoLine(p)} · {deviceLine(p)} · from {p.source || "Direct"}
                        </span>
                        <span className="mt-1 block text-xs">
                          {p.pages} pages · {p.actions} actions · stayed {duration(p.seconds)}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
                <div className="mt-3 hidden overflow-x-auto sm:block">
                  <table className="table min-w-[44rem]">
                    <thead>
                      <tr>
                        <th className="text-left">Who</th>
                        <th className="text-left">Device</th>
                        <th className="text-left">From</th>
                        <th className="text-left">Time</th>
                        <th className="text-right">Pages</th>
                        <th className="text-right">Actions</th>
                        <th className="text-right">Stayed</th>
                      </tr>
                    </thead>
                    <tbody>
                      {people.map((p) => (
                        <tr key={p.key}>
                          <td className="px-2 py-2">
                            <button type="button" className="text-left font-semibold hover:text-accent" onClick={() => onPerson(p.key)}>
                              {p.name}
                            </button>
                            <span className="block text-xs text-muted">{whoLine(p)}</span>
                          </td>
                          <td className="px-2 py-2 text-muted">{deviceLine(p)}</td>
                          <td className="px-2 py-2 text-muted">{p.source || "Direct"}</td>
                          <td className="px-2 py-2 whitespace-nowrap text-muted tabular-nums">
                            {clock(p.first)}
                            {p.last !== p.first && `–${clock(p.last)}`}
                          </td>
                          <td className="px-2 py-2 text-right tabular-nums">{p.pages}</td>
                          <td className="px-2 py-2 text-right tabular-nums">{p.actions}</td>
                          <td className="px-2 py-2 text-right tabular-nums">{duration(p.seconds)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <div className="grid gap-6 lg:grid-cols-2">
                <ListCard title="Pages" cols={["Views", "Avg time"]}>
                  {data.pages.map((p) => (
                    <Row key={p.path} name={p.name} a={p.views} b={duration(p.avg_s)} max={Math.max(...data.pages.map((x) => x.views), 1)} href={p.path} />
                  ))}
                </ListCard>
                <ListCard title="Actions" cols={["Times", "People"]}>
                  {data.actions.length === 0 && <li className="px-2 py-1.5 text-sm text-muted">No actions recorded on this day.</li>}
                  {data.actions.map((a) => (
                    <Row key={a.name} name={a.name} a={a.times} b={a.people} max={Math.max(...data.actions.map((x) => x.times), 1)} />
                  ))}
                </ListCard>
              </div>
              <HoursChart hours={data.hours} title="Hour by hour" />
            </>
          )}
        </>
      )}
    </div>
  );
}

function whoLine(p: DayPerson): string {
  const who = p.team || (p.staff ? "Staff" : p.signed_in ? "Signed in" : "Not signed in");
  return p.visits > 1 ? `${who} · ${p.visits} visits` : who;
}
