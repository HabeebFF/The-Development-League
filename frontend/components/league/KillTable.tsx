"use client";

import Link from "next/link";
import { useState } from "react";

import { plural } from "@/lib/league";
import type { KillList } from "@/lib/kills";

import { TeamMark } from "./TeamBadge";

const FIRST = 15; // rows shown before "Show all"

/** Every player's kills, knocks, headshot knocks and damage dealt, best first. */
export default function KillTable({ list, showMatches = true }: { list: KillList; showMatches?: boolean }) {
  const [all, setAll] = useState(false);
  if (!list.players.length) return <p className="text-sm text-muted">No kills to show.</p>;
  const rows = all ? list.players : list.players.slice(0, FIRST);
  const cell = "px-2 py-2 text-right tabular-nums";
  const damage = list.players.some((p) => p.damage != null);
  return (
    <>
      <div className="card overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th className="w-10 px-2 py-2 text-left">#</th>
              <th className="px-2 py-2 text-left">Player</th>
              <th className={cell}>Kills</th>
              <th className={cell}>Knocks</th>
              <th className={`${cell} hidden sm:table-cell`}>Headshots</th>
              {damage && <th className={`${cell} hidden sm:table-cell`}>Damage</th>}
              {showMatches && <th className={`${cell} hidden sm:table-cell`}>Matches</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.player_id} className={p.rank === 1 && p.kills > 0 ? "bg-[linear-gradient(90deg,rgb(255_194_61/0.10),transparent_60%)]" : ""}>
                <td className={`px-2 py-2.5 font-display text-lg ${p.rank <= 3 && p.kills > 0 ? "text-accent-2" : "text-muted"}`}>{p.rank}</td>
                <td className="max-w-[11rem] px-2 py-2 sm:max-w-none">
                  <span className="flex min-w-0 items-center gap-2.5">
                    {p.team && <TeamMark team={p.team} />}
                    <span className="min-w-0">
                      <span className="block truncate font-semibold">{p.player}</span>
                      {p.team && (
                        <Link href={`/teams/${p.team.slug}`} className="block truncate text-xs text-muted hover:text-accent">
                          {p.team.name}
                        </Link>
                      )}
                    </span>
                  </span>
                </td>
                <td className={`${cell} font-display text-xl text-white`}>{p.kills}</td>
                <td className={cell}>{p.knocks}</td>
                <td className={`${cell} hidden sm:table-cell`}>{p.headshots}</td>
                {damage && <td className={`${cell} hidden sm:table-cell`}>{p.damage == null ? "–" : p.damage.toLocaleString()}</td>}
                {showMatches && <td className={`${cell} hidden text-muted sm:table-cell`}>{p.matches}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted">
        <span>
          {plural(list.kills, "kill")} by {plural(list.players.length, "player")}
          {showMatches ? ` in ${list.matches} match${list.matches === 1 ? "" : "es"}` : ""}. Ties go to more knocks, then more headshot
          knocks.
        </span>
        {list.players.length > FIRST && (
          <button className="ml-auto text-accent hover:underline" onClick={() => setAll((a) => !a)}>
            {all ? "Show top 15" : `Show all ${list.players.length}`}
          </button>
        )}
      </div>
    </>
  );
}
