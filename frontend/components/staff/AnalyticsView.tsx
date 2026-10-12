"use client";

import Link from "next/link";
import { useState } from "react";

import { SkeletonRows } from "@/components/league/Loading";
import { type Analytics, compact, type Count, dayLabel, friendly, hourLabel, type PageCount, type Range, RANGES, share } from "@/lib/analytics";
import { useApi } from "@/lib/useApi";

/** Staff only: who is visiting the website, counted by the site itself (no cookies). */
export default function AnalyticsView() {
  const [range, setRange] = useState<Range>("7d");
  const { data, error } = useApi<Analytics>(`/analytics/summary?range=${range}`);

  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-5xl leading-none font-extrabold uppercase">Analytics</h1>
      <p className="mt-2 max-w-3xl text-sm text-muted">
        People visiting the website. No cookies: a visitor is the same phone or computer on the same day, so someone who comes back tomorrow counts again. Bots and staff are left out.
      </p>
      <div className="mt-6 flex gap-1 overflow-x-auto border-b border-line" role="tablist">
        {RANGES.map((r) => (
          <button
            key={r.key}
            role="tab"
            aria-selected={range === r.key}
            className={`-mb-px shrink-0 border-b-2 px-3 py-2 text-sm font-medium ${range === r.key ? "border-accent text-white" : "border-transparent text-muted hover:text-white"}`}
            onClick={() => setRange(r.key)}
          >
            {r.label}
          </button>
        ))}
      </div>

      {error && <p className="mt-6 text-bad">{error}</p>}
      {!data && !error && (
        <div className="mt-6">
          <SkeletonRows count={6} className="h-16" />
        </div>
      )}
      {data && <Report data={data} />}
    </section>
  );
}

function Report({ data }: { data: Analytics }) {
  const t = data.totals;
  return (
    <div className="mt-6 space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label="Visitors" value={compact(t.visitors)} />
        <Tile label="Page views" value={compact(t.views)} />
        <Tile label="Pages per visitor" value={String(t.pages_per_visitor)} />
        <Tile
          label="Online now"
          value={compact(t.online_now)}
          note="Last 5 minutes"
          dot={t.online_now > 0}
        />
      </div>
      {t.staff_views > 0 && <p className="text-xs text-muted">Not counted: {compact(t.staff_views)} page views by staff.</p>}

      {t.views === 0 ? (
        <div className="card p-6 text-sm text-muted">No visits in this period yet. Counting started when this page went live.</div>
      ) : (
        <>
          <DailyChart days={data.by_day} />
          <div className="grid gap-6 lg:grid-cols-2">
            <PageList pages={data.pages} />
            <CountList title="Where they came from" rows={data.sources} hint="Direct means typed in, a bookmark, or an app that hides where the link was opened (WhatsApp often does). Add ?ref=whatsapp to links you share to count them." />
            <CountList title="Devices" rows={data.devices} />
            <CountList title="Browsers" rows={data.browsers} />
            <CountList title="Systems" rows={data.systems} />
            <CountList title="Signed in" rows={data.audience} />
          </div>
          <HoursChart hours={data.hours} />
        </>
      )}
    </div>
  );
}

function Tile({ label, value, note, dot }: { label: string; value: string; note?: string; dot?: boolean }) {
  return (
    <div className="card p-4">
      <p className="text-xs font-semibold tracking-wider text-muted uppercase">{label}</p>
      <p className="mt-1 flex items-center gap-2 font-display text-4xl leading-none">
        {dot && <span className="inline-block h-2.5 w-2.5 rounded-full bg-ok shadow-[0_0_10px_var(--ok)]" aria-hidden />}
        {value}
      </p>
      {note && <p className="mt-1 text-xs text-muted">{note}</p>}
    </div>
  );
}

/** Vertical bars with a hover readout; `label` names a bar, `detail` is its full readout. */
function Bars({ values, label, detail, ticks }: { values: number[]; label: (i: number) => string; detail: (i: number) => string; ticks: number[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(...values, 1);
  return (
    <div>
      <div className="relative">
        <div className="h-5 text-xs text-white">{hover !== null ? detail(hover) : <span className="text-muted">Hover or tap a bar</span>}</div>
        <div className="relative mt-2 flex h-40 items-end gap-[2px] border-b border-line" onMouseLeave={() => setHover(null)}>
          <span className="pointer-events-none absolute top-0 left-0 text-[10px] text-muted">{compact(max)}</span>
          <div className="pointer-events-none absolute inset-x-0 top-0 border-t border-dashed border-line" />
          {values.map((v, i) => (
            <button
              key={i}
              type="button"
              aria-label={detail(i)}
              className="group flex h-full min-w-0 flex-1 items-end"
              onMouseEnter={() => setHover(i)}
              onFocus={() => setHover(i)}
              onClick={() => setHover(i)}
            >
              <span
                className={`block w-full rounded-t-[4px] transition-colors ${hover === i ? "bg-accent-hot" : "bg-accent/80 group-hover:bg-accent-hot"}`}
                style={{ height: `${v ? Math.max(2, (v / max) * 100) : 0}%` }}
              />
            </button>
          ))}
        </div>
      </div>
      <div className="relative mt-1 h-4 text-[10px] text-muted">
        {ticks.map((i) => (
          <span key={i} className="absolute -translate-x-1/2 whitespace-nowrap" style={{ left: `${((i + 0.5) / values.length) * 100}%` }}>
            {label(i)}
          </span>
        ))}
      </div>
    </div>
  );
}

function DailyChart({ days }: { days: Analytics["by_day"] }) {
  const n = days.length;
  const ticks = n <= 1 ? [0] : n <= 8 ? days.map((_, i) => i) : [0, Math.floor((n - 1) / 2), n - 1];
  const short = (iso: string) => (n <= 8 ? dayLabel(iso).split(" ")[0] : dayLabel(iso).split(" ").slice(1).join(" "));
  return (
    <div className="card p-4 sm:p-5">
      <h2 className="section-title">Visitors per day</h2>
      <div className="mt-4">
        <Bars
          values={days.map((d) => d.visitors)}
          label={(i) => short(days[i].date)}
          detail={(i) => `${dayLabel(days[i].date)}: ${compact(days[i].visitors)} visitors, ${compact(days[i].views)} page views`}
          ticks={ticks}
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
                <td className="px-2 py-1.5">{dayLabel(d.date)}</td>
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

function HoursChart({ hours }: { hours: Analytics["hours"] }) {
  return (
    <div className="card p-4 sm:p-5">
      <h2 className="section-title">Busiest hours</h2>
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

function ListCard({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="card p-4 sm:p-5">
      <h2 className="section-title">{title}</h2>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
      <div className="mt-3 flex justify-end gap-4 text-[11px] tracking-wider text-muted uppercase">
        <span className="w-16 text-right">Visitors</span>
        <span className="w-12 text-right">Views</span>
      </div>
      <ul className="mt-1 space-y-1">{children}</ul>
    </div>
  );
}

function Row({ name, views, visitors, max, href }: { name: string; views: number; visitors: number; max: number; href?: string }) {
  return (
    <li className="relative flex items-center gap-4 px-2 py-1.5 text-sm">
      <span className="absolute inset-y-0 left-0 bg-accent/15" style={{ width: `${share(visitors, max)}%` }} aria-hidden />
      <span className="relative min-w-0 flex-1 truncate">
        {href ? (
          <Link href={href} className="hover:text-accent">
            {name}
          </Link>
        ) : (
          name
        )}
      </span>
      <span className="relative w-16 text-right tabular-nums">{compact(visitors)}</span>
      <span className="relative w-12 text-right text-muted tabular-nums">{compact(views)}</span>
    </li>
  );
}

function PageList({ pages }: { pages: PageCount[] }) {
  const max = Math.max(...pages.map((p) => p.visitors), 1);
  return (
    <ListCard title="Top pages">
      {pages.map((p) => (
        <Row key={p.path} name={p.name} views={p.views} visitors={p.visitors} max={max} href={p.path} />
      ))}
    </ListCard>
  );
}

function CountList({ title, rows, hint }: { title: string; rows: Count[]; hint?: string }) {
  const max = Math.max(...rows.map((r) => r.visitors), 1);
  return (
    <ListCard title={title} hint={hint}>
      {rows.map((r) => (
        <Row key={r.name} name={friendly(r.name)} views={r.views} visitors={r.visitors} max={max} />
      ))}
    </ListCard>
  );
}
