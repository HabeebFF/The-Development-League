"use client";

import { useCallback, useSyncExternalStore } from "react";

import type { OddsFormat } from "@/lib/predictions";

const KEY = "tdl-odds-format";
const listeners = new Set<() => void>();

function read(): OddsFormat {
  try {
    return window.localStorage.getItem(KEY) === "fractional" ? "fractional" : "decimal";
  } catch {
    return "decimal";
  }
}

let current: OddsFormat | null = null;

function snapshot(): OddsFormat {
  if (current === null) current = read();
  return current;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** How this viewer likes odds shown (decimal unless they pick fractional), remembered in
 * this browser. Display only: bets are always placed and checked in decimal. */
export function useOddsFormat(): [OddsFormat, (format: OddsFormat) => void] {
  const format = useSyncExternalStore(subscribe, snapshot, () => "decimal" as OddsFormat);
  const set = useCallback((next: OddsFormat) => {
    current = next;
    try {
      window.localStorage.setItem(KEY, next);
    } catch {
      // Not remembered, but still switched on this page.
    }
    listeners.forEach((l) => l());
  }, []);
  return [format, set];
}
