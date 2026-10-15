"use client";

import Link from "next/link";
import { useState } from "react";

import { compact, share, type Who, WHO } from "@/lib/analytics";

export function Tile({ label, value, note, dot }: { label: string; value: string; note?: string; dot?: boolean }) {
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

export function Bars({ values, label, detail, ticks, onPick }: { values: number[]; label: (i: number) => string; detail: (i: number) => string; ticks: number[]; onPick?: (i: number) => void }) {
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
              onClick={() => (hover === i && onPick ? onPick(i) : setHover(i))}
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

export function ListCard({ title, hint, cols, children }: { title: string; hint?: string; cols: [string, string]; children: React.ReactNode }) {
  return (
    <div className="card p-4 sm:p-5">
      <h2 className="section-title">{title}</h2>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
      <div className="mt-3 flex justify-end gap-4 text-[11px] tracking-wider text-muted uppercase">
        <span className="w-16 text-right">{cols[0]}</span>
        <span className="w-14 text-right">{cols[1]}</span>
      </div>
      <ul className="mt-1 space-y-1">{children}</ul>
    </div>
  );
}

/** One list row: a bar sized by ``a`` (against ``max``), with two numbers on the right. */
export function Row({ name, a, b, max, href, note, onClick }: { name: string; a: string | number; b: string | number; max: number; href?: string; note?: string; onClick?: () => void }) {
  const value = typeof a === "number" ? a : 0;
  const label = href ? (
    <Link href={href} className="hover:text-accent">
      {name}
    </Link>
  ) : onClick ? (
    <button type="button" className="text-left hover:text-accent" onClick={onClick}>
      {name}
    </button>
  ) : (
    name
  );
  return (
    <li className="relative flex items-center gap-4 px-2 py-1.5 text-sm">
      <span className="absolute inset-y-0 left-0 bg-accent/15" style={{ width: `${share(value, max)}%` }} aria-hidden />
      <span className="relative min-w-0 flex-1 truncate">
        {label}
        {note && <span className="ml-2 text-xs text-muted">{note}</span>}
      </span>
      <span className="relative w-16 text-right tabular-nums">{typeof a === "number" ? compact(a) : a}</span>
      <span className="relative w-14 text-right text-muted tabular-nums">{typeof b === "number" ? compact(b) : b}</span>
    </li>
  );
}

/** Underlined tabs, like the coach page. */
export function Tabs<T extends string>({ tabs, value, onChange, small }: { tabs: { key: T; label: string }[]; value: T; onChange: (key: T) => void; small?: boolean }) {
  return (
    <div className="flex gap-1 overflow-x-auto border-b border-line" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={value === t.key}
          className={`-mb-px shrink-0 border-b-2 px-3 ${small ? "py-1.5 text-xs" : "py-2 text-sm"} font-medium ${value === t.key ? "border-accent text-white" : "border-transparent text-muted hover:text-white"}`}
          onClick={() => onChange(t.key)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

/** Everyone / signed in / not signed in / staff. */
export function WhoPicker({ value, onChange }: { value: Who; onChange: (who: Who) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5" aria-label="Who to show">
      {WHO.map((w) => (
        <button
          key={w.key}
          type="button"
          aria-pressed={value === w.key}
          className={`chip ${value === w.key ? "border-accent text-white" : "text-muted hover:text-white"}`}
          onClick={() => onChange(w.key)}
        >
          {w.label}
        </button>
      ))}
    </div>
  );
}
