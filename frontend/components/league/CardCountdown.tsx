"use client";

import { useEffect, useState } from "react";

import { countdown, nextRelease } from "@/lib/cards";

/** A ticking countdown to Saturday 11am, when the new cards come out. */
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
    <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border border-line bg-panel px-4 py-3 [clip-path:polygon(0_0,100%_0,100%_calc(100%-12px),calc(100%-12px)_100%,0_100%)]">
      <div>
        <p className="eyebrow">
          {justOut ? "New cards are out" : "Next cards drop"}
        </p>
        <p className="mt-1 text-sm text-muted">
          Every Saturday at 11am (Lagos time), for the week that ended Friday.{" "}
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
        className="flex gap-2"
        role="timer"
        aria-label={`${left.d} days ${left.h} hours ${left.m} minutes until new cards`}
      >
        {parts.map(([n, label]) => (
          <span
            key={label}
            className="flex min-w-14 flex-col items-center bg-bg px-2 py-1.5"
          >
            <span className="font-display text-3xl leading-none text-accent tabular-nums">
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
