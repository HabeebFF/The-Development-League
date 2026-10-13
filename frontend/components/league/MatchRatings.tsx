"use client";

import { Fragment, useState } from "react";

import { partText, pointsText, ratingText, type MatchRatings as Data } from "@/lib/ratings";

import RatingBadge from "./RatingBadge";
import { TeamMark } from "./TeamBadge";

const FIRST = 10;

/** Every player's rating in one match, best first; tap one to see how it was made. */
export default function MatchRatings({ data }: { data: Data }) {
  const [open, setOpen] = useState<number | null>(null);
  const [all, setAll] = useState(false);
  if (!data.players.length) return <p className="text-sm text-muted">No ratings for this match yet.</p>;
  const rows = all ? data.players : data.players.slice(0, FIRST);
  return (
    <>
      <div className="card overflow-x-auto">
        <table className="table">
          <tbody>
            {rows.map((p, i) => {
              const total = data.base + p.parts.reduce((s, x) => s + x.points, 0);
              return (
                <Fragment key={p.player_id}>
                  <tr className="cursor-pointer" onClick={() => setOpen(open === p.player_id ? null : p.player_id)} aria-expanded={open === p.player_id}>
                    <td className={`w-10 px-2 py-2.5 font-display text-lg ${i < 3 ? "text-accent-2" : "text-muted"}`}>{i + 1}</td>
                    <td className="max-w-[13rem] px-2 py-2 sm:max-w-none">
                      <span className="flex min-w-0 items-center gap-2.5">
                        {p.team && <TeamMark team={p.team} />}
                        <span className="min-w-0">
                          <span className="block truncate font-semibold">{p.player}</span>
                          <span className="block truncate text-xs text-muted">
                            {p.kills} K · {p.knocks} knocks{p.team ? ` · ${p.team.name}` : ""}
                          </span>
                        </span>
                      </span>
                    </td>
                    <td className="px-2 py-2 text-right">
                      <RatingBadge rating={p.rating} band={p.band} />
                    </td>
                  </tr>
                  {open === p.player_id && (
                    <tr className="bg-bg/50">
                      <td />
                      <td colSpan={2} className="px-2 py-2.5">
                        <ul className="max-w-sm space-y-1 text-xs">
                          <li className="flex justify-between gap-3 text-muted">
                            <span>Everyone starts on</span>
                            <span className="tabular-nums">{data.base.toFixed(2)}</span>
                          </li>
                          {p.parts.map((x) => (
                            <li key={x.key} className="flex justify-between gap-3">
                              <span>{partText(x)}</span>
                              <span className={`tabular-nums ${x.points > 0 ? "text-ok" : x.points < 0 ? "text-bad" : "text-muted"}`}>
                                {pointsText(x.points)}
                              </span>
                            </li>
                          ))}
                          <li className="flex justify-between gap-3 border-t border-line pt-1 font-semibold">
                            <span>Rating</span>
                            <span className="tabular-nums">
                              {ratingText(p.rating)}
                              {Math.abs(total - p.rating) >= 0.05 && <span className="font-normal text-muted"> (from {total.toFixed(2)})</span>}
                            </span>
                          </li>
                        </ul>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted">
        <span>Out of 10, like football. Tap a player to see how their rating was made.</span>
        {data.players.length > FIRST && (
          <button className="ml-auto text-accent hover:underline" onClick={() => setAll((a) => !a)}>
            {all ? `Show top ${FIRST}` : `Show all ${data.players.length}`}
          </button>
        )}
      </div>
    </>
  );
}
