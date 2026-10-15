"use client";

import { createContext, useCallback, useContext, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";

import type { SlipPick } from "@/lib/predictions";

type Slip = {
  picks: SlipPick[];
  open: boolean;
  setOpen: (open: boolean) => void;
  /** Add a choice, swap it for another choice on the same market, or take it off again. */
  toggle: (pick: SlipPick) => void;
  remove: (market: number) => void;
  setOdds: (market: number, odds: string) => void;
  clear: () => void;
  has: (outcome: number) => boolean;
};

const SlipContext = createContext<Slip | null>(null);
const KEY = "tdl-bet-slip";
const NONE: SlipPick[] = [];

// The picks live outside React, kept in this browser between visits. Storage can be blocked
// (private mode): then the slip still works until the page closes.
let current: SlipPick[] | null = null;
const listeners = new Set<() => void>();

function read(): SlipPick[] {
  if (current === null) {
    try {
      const raw = window.localStorage.getItem(KEY);
      const picks = raw ? JSON.parse(raw) : [];
      current = Array.isArray(picks) ? (picks as SlipPick[]) : [];
    } catch {
      current = [];
    }
  }
  return current;
}

function write(change: (picks: SlipPick[]) => SlipPick[]) {
  current = change(read());
  try {
    window.localStorage.setItem(KEY, JSON.stringify(current));
  } catch {
    // Not saved, but still on the page.
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The bet slip, shared by every prediction page. It only remembers taps: odds and
 * everything else are checked again by the server when the bet is placed. */
export function SlipProvider({ children }: { children: ReactNode }) {
  const picks = useSyncExternalStore(subscribe, read, () => NONE);
  const [open, setOpen] = useState(false);

  const toggle = useCallback(
    (pick: SlipPick) =>
      write((now) => {
        const same = now.find((p) => p.market === pick.market);
        if (same?.outcome === pick.outcome) return now.filter((p) => p.market !== pick.market);
        if (same) return now.map((p) => (p.market === pick.market ? pick : p));
        return [...now, pick];
      }),
    [],
  );
  const remove = useCallback((market: number) => write((now) => now.filter((p) => p.market !== market)), []);
  const setOdds = useCallback((market: number, odds: string) => write((now) => now.map((p) => (p.market === market ? { ...p, odds } : p))), []);
  const clear = useCallback(() => write(() => []), []);

  const value = useMemo<Slip>(
    () => ({ picks, open, setOpen, toggle, remove, setOdds, clear, has: (outcome) => picks.some((p) => p.outcome === outcome) }),
    [picks, open, toggle, remove, setOdds, clear],
  );
  return <SlipContext.Provider value={value}>{children}</SlipContext.Provider>;
}

export function useSlip(): Slip {
  const slip = useContext(SlipContext);
  if (!slip) throw new Error("useSlip needs a SlipProvider");
  return slip;
}
