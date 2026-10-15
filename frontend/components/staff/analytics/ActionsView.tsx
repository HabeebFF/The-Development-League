"use client";

import { useState } from "react";

import Loading from "@/components/league/Loading";
import { type ActionsReport, compact, dayLabel, type Range, RANGES, type Who } from "@/lib/analytics";
import { useApi } from "@/lib/useApi";

import { Bars, ListCard, Row, Tabs } from "./parts";

/** Every kind of action: how often, by how many people, per day and on which pages. */
export default function ActionsView({ who }: { who: Who }) {
  const [range, setRange] = useState<Range>("7d");
  const [path, setPath] = useState("");
  const { data, error } = useApi<ActionsReport>(`/analytics/actions?range=${range}&who=${who}&path=${encodeURIComponent(path)}`);
  const days = data?.by_day ?? [];
  const n = days.length;

  return (
    <div className="space-y-6">
      <Tabs tabs={RANGES} value={range} onChange={setRange} small />
      {path && (
        <p className="text-sm">
          Only on <span className="font-semibold">{data?.pages.find((p) => p.path === path)?.name ?? path}</span>{" "}
          <button type="button" className="text-xs text-accent hover:underline" onClick={() => setPath("")}>
            Show all pages
          </button>
        </p>
      )}
      {!data && <Loading error={error} count={6} />}
      {data && data.total === 0 && <div className="card p-6 text-sm text-muted">No actions recorded in this period.</div>}
      {data && data.total > 0 && (
        <>
          <div className="card p-4 sm:p-5">
            <h2 className="section-title">{compact(data.total)} actions</h2>
            <div className="mt-4">
              <Bars
                values={days.map((d) => d.actions)}
                label={(i) => dayLabel(days[i].date).split(" ").slice(n <= 8 ? 0 : 1, n <= 8 ? 1 : 3).join(" ")}
                detail={(i) => `${dayLabel(days[i].date)}: ${compact(days[i].actions)} actions`}
                ticks={n <= 1 ? [0] : n <= 8 ? days.map((_, i) => i) : [0, Math.floor((n - 1) / 2), n - 1]}
              />
            </div>
          </div>
          <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
            <div className="card overflow-x-auto p-2 sm:p-3">
              <table className="table min-w-[30rem]">
                <thead>
                  <tr>
                    <th className="text-left">Action</th>
                    <th className="text-right">Times</th>
                    <th className="text-right">People</th>
                  </tr>
                </thead>
                <tbody>
                  {data.actions.map((a) => (
                    <tr key={a.name}>
                      <td className="px-2 py-2">
                        {a.name}
                        {a.details.length > 0 && <span className="block text-xs text-muted">{a.details.map((d) => `${d.detail} (${d.times})`).join(" · ")}</span>}
                      </td>
                      <td className="px-2 py-2 text-right tabular-nums">{compact(a.times)}</td>
                      <td className="px-2 py-2 text-right tabular-nums">{compact(a.people)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ListCard title="By page" hint="Tap a page to see only its actions." cols={["Actions", ""]}>
              {data.pages.map((p) => (
                <Row key={p.path} name={p.name} a={p.actions} b="" max={Math.max(...data.pages.map((x) => x.actions), 1)} onClick={() => setPath(p.path)} />
              ))}
            </ListCard>
          </div>
        </>
      )}
    </div>
  );
}
