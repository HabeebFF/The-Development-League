"use client";

import Link from "next/link";
import { Fragment, useState } from "react";

import { plural } from "@/lib/league";
import { matchCount, type RatingBoard, type RatingRow } from "@/lib/ratings";

import RatingBadge from "./RatingBadge";
import { matchPlayers } from "./SearchBox";
import { TeamMark } from "./TeamBadge";

const FIRST = 15; // rows shown before "Show all"

/** The Player of the Day (or Session): big, on top of the table. */
export function StarPlayer({ row, label }: { row: RatingRow; label: string }) {
  return (
    <div className="card relative overflow-hidden p-5 sm:p-6">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgb(255_194_61/0.18),transparent_60%)]" />
      <div className="relative flex items-center gap-4">
        {row.team && (
          <span className="hidden sm:block">
            <TeamMark team={row.team} size="lg" />
          </span>
        )}
        <div className="min-w-0 flex-1">
          <p className="eyebrow text-accent-2">★ {label}</p>
          <p className="mt-1 truncate font-display text-2xl uppercase sm:text-4xl">{row.player}</p>
          <p className="mt-1 text-sm text-muted">
            {[row.team?.name, matchCount(row.matches), plural(row.kills, "kill"), `best ${row.best.toFixed(1)}`]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <RatingBadge rating={row.rating} band={row.band} size="lg" />
      </div>
    </div>
  );
}

/** Every player's average rating, best first; tap a player for each match's rating. */
export default function RatingTable({ board, limit, query = "" }: { board: RatingBoard; limit?: number; query?: string }) {
  const [all, setAll] = useState(false);
  const [open, setOpen] = useState<number | null>(null);
  if (!board.players.length) return <p className="text-sm text-muted">No ratings yet.</p>;
  const found = matchPlayers(board.players, query);
  if (!found.length) return <p className="text-sm text-muted">No player or team matches &ldquo;{query.trim()}&rdquo; here.</p>;
  const searching = found.length < board.players.length;
  const cap = limit ?? FIRST;
  const rows = (all && !limit) || searching ? found : found.slice(0, cap);
  const cell = "px-2 py-2 text-right tabular-nums";
  return (
    <>
      <div className="card overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th className="w-10 px-2 py-2 text-left">#</th>
              <th className="px-2 py-2 text-left">Player</th>
              <th className={`${cell} hidden sm:table-cell`}>Matches</th>
              <th className={`${cell} hidden sm:table-cell`}>Kills</th>
              <th className={cell}>Rating</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <Fragment key={p.player_id}>
                <tr
                  className={`cursor-pointer ${p.star ? "bg-[linear-gradient(90deg,rgb(255_194_61/0.10),transparent_60%)]" : ""}`}
                  onClick={() => setOpen(open === p.player_id ? null : p.player_id)}
                  aria-expanded={open === p.player_id}
                >
                  <td className={`px-2 py-2.5 font-display text-lg ${p.rank <= 3 ? "text-accent-2" : "text-muted"}`}>{p.rank}</td>
                  <td className="max-w-[13rem] px-2 py-2 sm:max-w-none">
                    <span className="flex min-w-0 items-center gap-2.5">
                      {p.team && <TeamMark team={p.team} />}
                      <span className="min-w-0">
                        <span className="block truncate font-semibold">
                          {p.player}
                          {p.star && <span className="ml-1.5 text-accent-2" title="Player of the Day">★</span>}
                        </span>
                        <span className="block truncate text-xs text-muted">
                          {p.team?.name ?? ""}
                          <span className="sm:hidden">
                            {p.team ? " · " : ""}
                            {p.matches} M · {plural(p.kills, "kill")}
                          </span>
                        </span>
                      </span>
                    </span>
                  </td>
                  <td className={`${cell} hidden text-muted sm:table-cell`}>{p.matches}</td>
                  <td className={`${cell} hidden sm:table-cell`}>{p.kills}</td>
                  <td className={cell}>
                    <RatingBadge rating={p.rating} band={p.band} />
                  </td>
                </tr>
                {open === p.player_id && (
                  <tr className="bg-bg/50">
                    <td />
                    <td colSpan={4} className="px-2 py-2.5">
                      <div className="flex flex-wrap gap-2">
                        {p.ratings.map((r) => (
                          <Link
                            key={r.match}
                            href={`/matches/${r.match}`}
                            className="flex items-center gap-2 rounded-sm border border-line px-2 py-1 text-xs hover:border-accent"
                            title={r.session}
                          >
                            <span className="text-muted">{r.label}</span>
                            <RatingBadge rating={r.rating} band={r.band} size="sm" />
                          </Link>
                        ))}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {!limit && (
        <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted">
          <span>
            {searching && `${plural(found.length, "player")} found · `}
            The average of each player&apos;s match ratings. Tap a player for every match. The top player (★) needs {matchCount(board.need)}.
          </span>
          {!searching && board.players.length > FIRST && (
            <button className="ml-auto text-accent hover:underline" onClick={() => setAll((a) => !a)}>
              {all ? "Show top 15" : `Show all ${board.players.length}`}
            </button>
          )}
        </div>
      )}
    </>
  );
}
