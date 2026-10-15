"use client";

import { useState } from "react";

import { SkeletonRows } from "@/components/league/Loading";
import { type Analytics, compact, type Count, dayLabel, duration, friendly, hourLabel, type Range, RANGES, type Who } from "@/lib/analytics";
import { useApi } from "@/lib/useApi";

import { Bars, ListCard, Row, Tabs, Tile } from "./parts";

/** Totals, charts and top lists for a date range. */
export default function Overview({ who, onDay }: { who: Who; onDay: (date: string) => void }) {
  const [range, setRange] = useState<Range>("7d");
  const { data, error } = useApi<Analytics>(`/analytics/summary?range=${range}&who=${who}`);
  return (
    <div>
      <Tabs tabs={RANGES} value={range} onChange={setRange} small />
      {error && <p className="mt-6 text-bad">{error}</p>}
      {!data && !error && (
        <div className="mt-6">
          <SkeletonRows count={6} className="h-16" />
        </div>
      )}
      {data && <Report data={data} who={who} onDay={onDay} />}
    </div>
  );
}

function Report({ data, who, onDay }: { data: Analytics; who: Who; onDay: (date: string) => void }) {
  const t = data.totals;
  return (
    <div className="mt-6 space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label="Visitors" value={compact(t.visitors)} />
        <Tile label="Page views" value={compact(t.views)} note={`${t.pages_per_visitor} per visitor`} />
        <Tile label="Online now" value={compact(t.online_now)} note="Last 5 minutes" dot={t.online_now > 0} />
        <Tile label="Actions" value={compact(t.actions)} note="Clicks, picks and saves" />
        <Tile label="Visits" value={compact(t.visits)} />
        <Tile label="Time per visit" value={duration(t.avg_visit_s)} note="Average" />
        <Tile label="Left after one page" value={`${t.bounce_rate}%`} note="Of visits, doing nothing else" />
      </div>
      {who !== "staff" && t.staff_views > 0 && <p className="text-xs text-muted">Not counted: {compact(t.staff_views)} page views by staff.</p>}

      {t.views === 0 ? (
        <div className="card p-6 text-sm text-muted">No visits in this period yet.</div>
      ) : (
        <>
          <DailyChart days={data.by_day} onDay={onDay} />
          <div className="grid gap-6 lg:grid-cols-2">
            <ListCard title="Top pages" cols={["Visitors", "Avg time"]}>
              {data.pages.map((p) => (
                <Row key={p.path} name={p.name} a={p.visitors} b={duration(p.avg_s)} max={Math.max(...data.pages.map((x) => x.visitors), 1)} href={p.path} />
              ))}
            </ListCard>
            <ListCard title="Top actions" cols={["Times", "People"]}>
              {data.actions.length === 0 && <li className="px-2 py-1.5 text-sm text-muted">No actions recorded yet.</li>}
              {data.actions.map((a) => (
                <Row key={a.name} name={a.name} a={a.times} b={a.people} max={Math.max(...data.actions.map((x) => x.times), 1)} />
              ))}
            </ListCard>
            <CountList
              title="Where they came from"
              rows={data.sources}
              hint="Direct means typed in, a bookmark, or an app that hides where the link was opened (WhatsApp often does). Add ?ref=whatsapp to links you share to count them."
            />
            <CountList title="Devices" rows={data.devices} />
            <CountList title="Browsers" rows={data.browsers} />
            <CountList title="Systems" rows={data.systems} />
          </div>
          <HoursChart hours={data.hours} />
        </>
      )}
    </div>
  );
}

function DailyChart({ days, onDay }: { days: Analytics["by_day"]; onDay: (date: string) => void }) {
  const n = days.length;
  const ticks = n <= 1 ? [0] : n <= 8 ? days.map((_, i) => i) : [0, Math.floor((n - 1) / 2), n - 1];
  const short = (iso: string) => (n <= 8 ? dayLabel(iso).split(" ")[0] : dayLabel(iso).split(" ").slice(1).join(" "));
  return (
    <div className="card p-4 sm:p-5">
      <h2 className="section-title">Visitors per day</h2>
      <p className="mt-1 text-xs text-muted">Click a day (tap twice on a phone) to see it in detail.</p>
      <div className="mt-4">
        <Bars
          values={days.map((d) => d.visitors)}
          label={(i) => short(days[i].date)}
          detail={(i) => `${dayLabel(days[i].date)}: ${compact(days[i].visitors)} visitors, ${compact(days[i].views)} page views`}
          ticks={ticks}
          onPick={(i) => onDay(days[i].date)}
        />
      </div>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-xs text-muted hover:text-white">Show as a table</summary>
        <table className="table mt-2">
          <thead>
            <tr>
              <th className="text-left">Day</th>
              <th className="text-right">Visitors</th>
              <th className="text-right">Page views</th>
            </tr>
          </thead>
          <tbody>
            {[...days].reverse().map((d) => (
              <tr key={d.date}>
                <td className="px-2 py-1.5">
                  <button type="button" className="hover:text-accent" onClick={() => onDay(d.date)}>
                    {dayLabel(d.date)}
                  </button>
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums">{compact(d.visitors)}</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{compact(d.views)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

export function HoursChart({ hours, title = "Busiest hours" }: { hours: { hour: number; views: number }[]; title?: string }) {
  return (
    <div className="card p-4 sm:p-5">
      <h2 className="section-title">{title}</h2>
      <p className="mt-1 text-xs text-muted">Page views by hour of the day, Lagos time.</p>
      <div className="mt-4">
        <Bars
          values={hours.map((h) => h.views)}
          label={(i) => hourLabel(hours[i].hour)}
          detail={(i) => `${hourLabel(hours[i].hour)} to ${hourLabel((hours[i].hour + 1) % 24)}: ${compact(hours[i].views)} page views`}
          ticks={[0, 6, 12, 18, 23]}
        />
      </div>
    </div>
  );
}

function CountList({ title, rows, hint }: { title: string; rows: Count[]; hint?: string }) {
  const max = Math.max(...rows.map((r) => r.visitors), 1);
  return (
    <ListCard title={title} hint={hint} cols={["Visitors", "Views"]}>
      {rows.map((r) => (
        <Row key={r.name} name={friendly(r.name)} a={r.visitors} b={r.views} max={max} />
      ))}
    </ListCard>
  );
}
