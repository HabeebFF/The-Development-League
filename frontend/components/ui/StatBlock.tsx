"use client";

import { useCountUp } from "@/lib/useCountUp";

import Card from "./Card";

/** A label, a big number that counts up when it scrolls in, and an optional change with an arrow. */
export default function StatBlock({
  label,
  value,
  decimals = 0,
  suffix,
  delta,
  deltaLabel,
}: {
  label: string;
  value: number | null;
  decimals?: number;
  suffix?: string;
  /** Positive is up (green), negative down (red), zero no change. */
  delta?: number | null;
  /** Shown after the delta ("this week"). */
  deltaLabel?: string;
}) {
  const [ref, shown] = useCountUp(value ?? 0, decimals);
  const dir = delta == null ? null : delta > 0 ? "up" : delta < 0 ? "down" : "same";
  return (
    <Card className="px-4 py-4 sm:px-5">
      <p className="text-[11px] font-bold tracking-[0.2em] text-muted uppercase">{label}</p>
      <p className="num mt-2 text-5xl leading-none">
        <span ref={ref}>{value == null ? "–" : shown}</span>
        {suffix && <span className="ml-1 text-base tracking-[0.12em] text-muted">{suffix}</span>}
      </p>
      {dir && (
        <p className={`mt-1.5 font-display text-sm font-extrabold ${dir === "up" ? "text-up" : dir === "down" ? "text-down" : "text-same"}`}>
          {dir === "up" ? "▲" : dir === "down" ? "▼" : "–"} {dir === "up" ? "+" : ""}
          {delta}
          {deltaLabel && <span className="ml-1 font-semibold">{deltaLabel}</span>}
        </p>
      )}
    </Card>
  );
}
