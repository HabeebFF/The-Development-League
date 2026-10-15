"use client";

import { useState } from "react";

import Loading from "@/components/league/Loading";
import { type Account, clock, dayLabel, duration, leagueToday } from "@/lib/analytics";
import { useApi } from "@/lib/useApi";

import { Tabs } from "./parts";

const SPANS = [
  { key: "7", label: "7 days" },
  { key: "30", label: "30 days" },
  { key: "90", label: "90 days" },
];

/** Every signed-in account seen lately; open one to see the days they came. */
export default function PeopleView({ onOpen }: { onOpen: (person: string, date: string) => void }) {
  const [days, setDays] = useState("30");
  const [open, setOpen] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const { data, error } = useApi<{ days: number; people: Account[] }>(`/analytics/people?days=${days}`);
  const people = (data?.people ?? []).filter((p) => !query || `${p.name} ${p.team}`.toLowerCase().includes(query.toLowerCase()));

  return (
    <div className="space-y-4">
      <Tabs tabs={SPANS} value={days} onChange={setDays} small />
      <p className="text-xs text-muted">People with an account, most recent first. Visitors without an account cannot be followed across days, so they are only in Day by day.</p>
      <input type="search" className="input max-w-xs" placeholder="Find a name or team" value={query} onChange={(e) => setQuery(e.target.value)} />
      {!data && <Loading error={error} count={6} />}
      {data && people.length === 0 && <div className="card p-6 text-sm text-muted">No signed-in visits in this period.</div>}
      {data && people.length > 0 && (
        <div className="card overflow-x-auto p-2 sm:p-3">
          <table className="table min-w-[40rem]">
            <thead>
              <tr>
                <th className="text-left">Who</th>
                <th className="text-left">Last seen</th>
                <th className="text-right">Days</th>
                <th className="text-right">Pages</th>
                <th className="text-right">Actions</th>
                <th className="text-right">Time</th>
              </tr>
            </thead>
            <tbody>
              {people.map((p) => (
                <PersonRow key={p.key} p={p} open={open === p.key} onToggle={() => setOpen(open === p.key ? null : p.key)} onOpen={onOpen} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function PersonRow({ p, open, onToggle, onOpen }: { p: Account; open: boolean; onToggle: () => void; onOpen: (person: string, date: string) => void }) {
  return (
    <>
      <tr>
        <td className="px-2 py-2">
          <button type="button" className="text-left font-semibold hover:text-accent" onClick={onToggle} aria-expanded={open}>
            {p.name}
          </button>
          <span className="block text-xs text-muted">
            {p.team || (p.staff ? "Staff" : "No team")}
            {p.new && <span className="ml-2 chip text-accent">New</span>}
          </span>
        </td>
        <td className="px-2 py-2 whitespace-nowrap text-muted">
          {dayLabel(leagueToday(new Date(p.last)))} {clock(p.last)}
        </td>
        <td className="px-2 py-2 text-right tabular-nums">{p.days_active}</td>
        <td className="px-2 py-2 text-right tabular-nums">{p.pages}</td>
        <td className="px-2 py-2 text-right tabular-nums">{p.actions}</td>
        <td className="px-2 py-2 text-right tabular-nums">{duration(p.seconds)}</td>
      </tr>
      {open && (
        <tr>
          <td colSpan={6} className="px-2 pb-3">
            <div className="flex flex-wrap gap-1.5">
              {p.by_day.map((d) => (
                <button key={d.date} type="button" className="chip hover:border-accent hover:text-white" onClick={() => onOpen(p.key, d.date)}>
                  {dayLabel(d.date)} · {d.pages} pages
                </button>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
