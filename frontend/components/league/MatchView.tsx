"use client";

import Link from "next/link";
import { Fragment, useState } from "react";

import { mapName, ordinal, plural, shortDate, type MatchDetail } from "@/lib/league";
import { clock } from "@/lib/replay";
import { useApi } from "@/lib/useApi";

import Loading from "./Loading";
import PageHeader from "./PageHeader";
import TeamBadge from "./TeamBadge";

/** One match: every team's placement, kills and points; tap a team for its players. */
export default function MatchView({ id }: { id: number }) {
  const match = useApi<MatchDetail>(`/matches/${id}`);
  const [open, setOpen] = useState<Set<number>>(new Set());
  if (!match.data)
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        <Loading error={match.error} count={10} />
      </div>
    );
  const m = match.data;

  function toggle(teamId: number) {
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(teamId)) next.delete(teamId);
      else next.add(teamId);
      return next;
    });
  }

  const cell = "px-2 py-2 text-right tabular-nums";
  return (
    <>
      <PageHeader eyebrow={mapName(m.map)} title={`Match ${m.number}`}>
        {[shortDate(m.started_at), m.duration_s ? `${clock(m.duration_s)} long` : null].filter(Boolean).join(" · ")}
        {m.vod_url && (
          <a href={m.vod_url} target="_blank" rel="noreferrer" className="btn btn-primary mt-4 flex w-fit">
            Watch the match
          </a>
        )}
      </PageHeader>
      <div className="mx-auto max-w-6xl px-4 py-8">
        <Link href={`/results/${m.match_day}`} className="text-xs font-bold tracking-widest text-muted uppercase hover:text-accent">
          &larr; Match day
        </Link>
        <div className="card mt-4 overflow-x-auto">
          <table className="table">
            <thead>
              <tr>
                <th className="px-2 py-2 text-left">Place</th>
                <th className="px-2 py-2 text-left">Team</th>
                <th className={cell}>Kills</th>
                <th className={`${cell} hidden sm:table-cell`}>Place pts</th>
                <th className={`${cell} hidden sm:table-cell`}>Kill pts</th>
                <th className={cell}>Total</th>
              </tr>
            </thead>
            <tbody>
              {m.results.map((r) => (
                <Fragment key={r.team.id}>
                  <tr
                    className={`cursor-pointer ${r.booyah ? "bg-[linear-gradient(90deg,rgb(255_194_61/0.10),transparent_60%)]" : ""}`}
                    onClick={() => toggle(r.team.id)}
                    aria-expanded={open.has(r.team.id)}
                  >
                    <td className={`px-2 py-2.5 font-display text-lg uppercase ${r.booyah ? "text-accent-2" : "text-muted"}`}>
                      {r.booyah ? "Booyah" : ordinal(r.placement)}
                    </td>
                    <td className="max-w-[8rem] px-2 py-2 sm:max-w-none">
                      <TeamBadge team={r.team} link={false} />
                    </td>
                    <td className={cell}>{r.kills}</td>
                    <td className={`${cell} hidden sm:table-cell`}>{r.placement_points}</td>
                    <td className={`${cell} hidden sm:table-cell`}>{r.kill_points}</td>
                    <td className={`${cell} font-display text-xl text-white`}>{r.total_points}</td>
                  </tr>
                  {open.has(r.team.id) && (
                    <tr className="bg-bg/50">
                      <td />
                      <td colSpan={5} className="px-2 py-2">
                        <ul className="space-y-1">
                          {r.players.map((p) => (
                            <li key={p.game_uid} className="flex gap-3 text-xs">
                              <span className="flex-1 truncate">
                                {p.display_name}
                                {p.is_mvp && <span className="ml-2 text-accent-2">MVP</span>}
                              </span>
                              <span className="text-muted">{plural(p.kills, "kill")}</span>
                              <span className="hidden text-muted sm:inline">{plural(p.knocks, "knock")}</span>
                            </li>
                          ))}
                          {!r.players.length && <li className="text-xs text-muted">No player stats.</li>}
                        </ul>
                        <Link href={`/teams/${r.team.slug}`} className="mt-2 inline-block text-xs text-accent">
                          Team page &rarr;
                        </Link>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-muted">Tap a team to see its players.</p>
      </div>
    </>
  );
}
