"use client";

import Link from "next/link";
import { useState } from "react";

import { monthLabel, type TeamOfMonth as Month } from "@/lib/cards";
import { useApi } from "@/lib/useApi";

import Loading from "./Loading";
import PlayerCard from "./PlayerCard";

/** Team of the Month: the month's top player, rusher, sniper and grenader on special cards. */
export default function TeamOfMonth() {
  const [month, setMonth] = useState<string | null>(null);
  const data = useApi<Month>(`/cards/month${month ? `?month=${month}` : ""}`);
  const m = data.data;

  if (!m) return <Loading error={data.error} count={4} />;
  if (!m.month)
    return (
      <p className="text-muted">
        No cards yet. They come out every Saturday at 11am for the week before.
      </p>
    );
  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <span className="ml-auto flex items-center gap-2">
          <button
            className="btn px-3 py-1.5 text-sm"
            disabled={!m.previous}
            onClick={() => setMonth(m.previous)}
            aria-label="Earlier month"
          >
            &larr;
          </button>
          <span className="min-w-40 text-center font-display text-lg uppercase">
            {monthLabel(m.month)}
          </span>
          <button
            className="btn px-3 py-1.5 text-sm"
            disabled={!m.next}
            onClick={() => setMonth(m.next)}
            aria-label="Later month"
          >
            &rarr;
          </button>
        </span>
      </div>
      <p className="mt-3 text-sm text-muted">
        The month&apos;s award winners on the card they ended the month with.
        {m.finished === false &&
          " The month isn't over yet, so this can still change."}
      </p>
      <div className="mt-6 grid grid-cols-2 justify-items-center gap-x-3 gap-y-6 lg:grid-cols-4">
        {m.slots.map((s) => (
          <div key={s.award} className="flex flex-col items-center gap-2">
            <p className="font-display text-lg text-accent uppercase">
              {s.title}
            </p>
            {s.card ? (
              <Link
                href={`/cards/${s.card.player_id}?week=${s.card.week}`}
                className="transition duration-200 hover:-translate-y-1"
                aria-label={`${s.title}: ${s.card.name}, ${s.card.overall}`}
              >
                <span className="sm:hidden">
                  <PlayerCard card={s.card} size={0.64} />
                </span>
                <span className="hidden sm:block">
                  <PlayerCard card={s.card} size={0.85} />
                </span>
              </Link>
            ) : (
              <p className="flex aspect-[5/7] w-[9.6em] items-center justify-center border border-dashed border-line p-3 text-center text-xs text-muted sm:w-[12.75em]">
                {s.detail || "No winner yet"}
              </p>
            )}
            {s.card && (
              <p className="max-w-[12em] text-center text-xs text-muted">
                {s.detail}
              </p>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
