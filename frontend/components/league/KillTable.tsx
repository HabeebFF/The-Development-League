"use client";

import Link from "next/link";
import { useState } from "react";

import { plural } from "@/lib/league";
import type { KillList } from "@/lib/kills";

import RankBadge from "@/components/ui/RankBadge";

import { matchPlayers } from "./SearchBox";
import { TeamMark } from "./TeamBadge";

const FIRST = 15; // rows shown before "Show all"

/** Every player's kills, knocks, headshot knocks and damage dealt, best first. */
export default function KillTable({ list, showMatches = true, query = "" }: { list: KillList; showMatches?: boolean; query?: string }) {
  const [all, setAll] = useState(false);
  if (!list.players.length) return <p className="text-sm text-muted">No kills to show.</p>;
  const found = matchPlayers(list.players, query);
  if (!found.length) return <p className="text-sm text-muted">No player or team matches &ldquo;{query.trim()}&rdquo; here.</p>;
  const searching = found.length < list.players.length;
  const rows = all || searching ? found : found.slice(0, FIRST);
  const cell = "px-2 py-2 text-right tabular-nums";
  const damage = list.players.some((p) => p.damage != null);
  const weapons = list.players.some((p) => p.weapon);
  return (
    <>
      <div className="card overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th className="w-14 px-2 py-2 text-left">#</th>
              <th className="px-2 py-2 text-left">Player</th>
              <th className={cell}>Kills</th>
              <th className={cell}>Knocks</th>
              <th className={`${cell} hidden sm:table-cell`}>Headshots</th>
              <th className={cell} title="Headshot knocks as a share of knocks">HS%</th>
              {weapons && <th className="hidden px-2 py-2 text-left md:table-cell">Main weapon</th>}
              {damage && <th className={`${cell} hidden sm:table-cell`}>Damage</th>}
              {showMatches && <th className={`${cell} hidden sm:table-cell`}>Matches</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.player_id} className={p.rank === 1 && p.kills > 0 ? "bg-[linear-gradient(90deg,rgb(246_197_68/0.14),transparent_60%)]" : ""}>
                <td className="px-2 py-2">{p.kills > 0 ? <RankBadge rank={p.rank} /> : <span className="font-display text-lg text-muted">{p.rank}</span>}</td>
                <td className="max-w-[11rem] px-2 py-2 sm:max-w-none">
                  <span className="flex min-w-0 items-center gap-2.5">
                    {p.team && <TeamMark team={p.team} />}
                    <span className="min-w-0">
                      <span className="block truncate font-display text-base font-extrabold uppercase">{p.player}</span>
                      {p.team && (
                        <Link href={`/teams/${p.team.slug}`} className="block truncate text-xs text-muted hover:text-accent">
                          {p.team.name}
                        </Link>
                      )}
                    </span>
                  </span>
                </td>
                <td className={`${cell} font-display text-2xl font-black text-accent-hot`}>{p.kills}</td>
                <td className={cell}>{p.knocks}</td>
                <td className={`${cell} hidden sm:table-cell`}>{p.headshots}</td>
                <td className={`${cell} text-muted`}>{p.hs_pct == null ? "–" : `${p.hs_pct}%`}</td>
                {weapons && (
                  <td className="hidden px-2 py-2 text-left text-sm md:table-cell" title={p.weapon ? `${p.weapon.uses} kills and knocks, ${p.weapon.share}% of theirs` : undefined}>
                    {p.weapon ? p.weapon.name : <span className="text-muted">–</span>}
                  </td>
                )}
                {damage && <td className={`${cell} hidden sm:table-cell`}>{p.damage == null ? "–" : p.damage.toLocaleString()}</td>}
                {showMatches && <td className={`${cell} hidden text-muted sm:table-cell`}>{p.matches}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted">
        <span>
          {searching && `${plural(found.length, "player")} found · `}
          {plural(list.kills, "kill")} by {plural(list.players.length, "player")}
          {showMatches ? ` in ${list.matches} match${list.matches === 1 ? "" : "es"}` : ""}. Ties go to more knocks, then more headshot
          knocks. HS% is headshot knocks out of knocks (the game only marks headshots on knocks).
        </span>
        {!searching && list.players.length > FIRST && (
          <button className="ml-auto text-accent hover:underline" onClick={() => setAll((a) => !a)}>
            {all ? "Show top 15" : `Show all ${list.players.length}`}
          </button>
        )}
      </div>
    </>
  );
}
