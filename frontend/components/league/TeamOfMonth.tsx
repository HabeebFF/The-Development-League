"use client";

import { useState } from "react";

import { monthLabel, type TeamOfMonth as Month } from "@/lib/cards";
import { useApi } from "@/lib/useApi";

import AwardSlots from "./AwardSlots";
import Loading from "./Loading";

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
      <AwardSlots
        kind="totm"
        period={m.month}
        periodLabel={monthLabel(m.month)}
        slots={m.slots}
        faceDown={!!m.newest}
      />
    </>
  );
}
