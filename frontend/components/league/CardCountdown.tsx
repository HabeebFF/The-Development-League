"use client";

import { useEffect, useState } from "react";

import { countdown, nextRelease } from "@/lib/cards";

/** A ticking countdown to midnight on Friday night (Lagos), when the new cards come out. */
export default function CardCountdown() {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    const tick = () => setNow(new Date());
    const first = setTimeout(tick, 0);
    const id = setInterval(tick, 1000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, []);
  // Rendered on the server first: wait for the browser's clock so the numbers don't jump.
  if (!now) return <div className="h-[5.5rem]" />;
  const to = nextRelease(now);
  const left = countdown(now, to);
  // The first hour after a release: the new cards are being built and are out.
  const justOut = now.getTime() - (to.getTime() - 7 * 86400_000) < 3600_000;
  const parts: [number, string][] = [
    [left.d, "days"],
    [left.h, "hrs"],
    [left.m, "min"],
    [left.s, "sec"],
  ];
  return (
    <div className="relative mb-6 flex flex-wrap items-center justify-between gap-4 overflow-hidden border-t-4 border-lion bg-panel px-4 py-4 [clip-path:polygon(0_0,100%_0,100%_calc(100%-12px),calc(100%-12px)_100%,0_100%)] sm:px-6">
      <span aria-hidden className="hex-grid pointer-events-none absolute inset-0 opacity-50" />
      <span aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_90%_at_100%_0%,rgb(245_165_36/0.18),transparent_70%)]" />
      <div className="relative">
        <p className="eyebrow">
          {justOut ? "New cards are out" : "Next cards drop"}
        </p>
        <p className="mt-1 font-display text-3xl leading-none font-black uppercase sm:text-4xl">New every Saturday</p>
        <p className="mt-1 text-sm text-muted">
          Every Saturday at midnight (Lagos time), as soon as the week ends on
          Friday night.{" "}
          {/* Lagos is UTC+1 all year: only show the viewer's own time when it differs. */}
          {to.getTimezoneOffset() !== -60 && (
            <span className="whitespace-nowrap">
              Your time:{" "}
              {to.toLocaleString(undefined, {
                weekday: "short",
                hour: "numeric",
                minute: "2-digit",
              })}
            </span>
          )}
        </p>
      </div>
      <div
        className="relative flex gap-2"
        role="timer"
        aria-label={`${left.d} days ${left.h} hours ${left.m} minutes until new cards`}
      >
        {parts.map(([n, label]) => (
          <span
            key={label}
            className="flex min-w-14 flex-col items-center border border-line bg-bg px-2 py-1.5"
          >
            <span className="num text-3xl leading-none text-accent-hot">
              {String(n).padStart(2, "0")}
            </span>
            <span className="mt-1 text-[10px] font-bold tracking-widest text-muted uppercase">
              {label}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
