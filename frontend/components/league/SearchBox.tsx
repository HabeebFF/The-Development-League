"use client";

import type { TeamRef } from "@/lib/api";

/** A player or team search box that filters the table under it. */
export default function SearchBox({ value, onChange, label = "Search players or teams" }: { value: string; onChange: (v: string) => void; label?: string }) {
  return (
    <div className="relative w-full sm:max-w-sm">
      <svg viewBox="0 0 20 20" aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted">
        <path fill="currentColor" d="M8.5 3a5.5 5.5 0 0 1 4.38 8.82l3.65 3.65-1.06 1.06-3.65-3.65A5.5 5.5 0 1 1 8.5 3Zm0 1.5a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z" />
      </svg>
      <input
        type="search"
        className="input pl-9 pr-9"
        placeholder={label}
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete="off"
        enterKeyHint="search"
      />
      {value && (
        <button
          type="button"
          className="absolute right-2 top-1/2 -translate-y-1/2 px-1.5 text-lg leading-none text-muted hover:text-text"
          onClick={() => onChange("")}
          aria-label="Clear search"
        >
          &times;
        </button>
      )}
    </div>
  );
}

/** Lowercase, no spaces or punctuation, so "vt timmyy" finds "VT TIMMYY!!" and "VT.TIMMYY". */
function squash(s: string): string {
  return s.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}

/** Rows whose player name, team name or team tag contain the search; all rows when it is empty. */
export function matchPlayers<T extends { player: string; team: TeamRef | null }>(rows: T[], query: string): T[] {
  const q = squash(query);
  if (!q) return rows;
  return rows.filter((r) => [r.player, r.team?.name, r.team?.tag].some((s) => s && squash(s).includes(q)));
}
