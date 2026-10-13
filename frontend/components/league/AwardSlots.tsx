"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { flipId, readFlipped, saveFlipped, type AwardSlot } from "@/lib/cards";

import FlipCard, { LockedCard } from "./FlipCard";
import PlayerCard from "./PlayerCard";

/** Team of the Week or Month: one card per award. The newest week or month starts face
 * down, and each visitor turns the cards over themselves (remembered in their browser). */
export default function AwardSlots({
  kind,
  period,
  periodLabel,
  slots,
  faceDown,
  lockedNote,
}: {
  kind: "totw" | "totm";
  /** The week's Saturday or the month's first day. */
  period: string;
  periodLabel: string;
  slots: AwardSlot[];
  faceDown: boolean;
  /** The period isn't over: every slot stays face down with this note ("Opens 1 Nov"). */
  lockedNote?: string;
}) {
  const [flipped, setFlipped] = useState<Set<string>>(new Set());
  const [ready, setReady] = useState(false);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    // After the first paint: the server can't know what this browser has opened.
    const id = window.setTimeout(() => {
      setFlipped(readFlipped());
      window.setTimeout(() => setReady(true), 50);
    }, 0);
    const pending = timers.current;
    return () => {
      window.clearTimeout(id);
      pending.forEach((t) => window.clearTimeout(t));
    };
  }, []);

  const ids = slots.map((s) =>
    s.card ? flipId(kind, period, s.award, s.card.player_id) : null,
  );
  const hidden = faceDown
    ? ids.filter((id): id is string => !!id && !flipped.has(id))
    : [];

  function flip(id: string) {
    setFlipped((now) => {
      const next = new Set(now).add(id);
      saveFlipped(next);
      return next;
    });
  }

  function revealAll() {
    hidden.forEach((id, i) => {
      timers.current.push(window.setTimeout(() => flip(id), i * 350));
    });
  }

  return (
    <>
      {faceDown && !lockedNote && slots.some((s) => s.card) && (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <p className="text-sm text-muted">
            {hidden.length ? "Tap a card to turn it over." : "All revealed."}
          </p>
          {hidden.length > 1 && (
            <button
              className="btn btn-primary px-3 py-1.5 text-sm uppercase"
              onClick={revealAll}
            >
              Reveal all
            </button>
          )}
        </div>
      )}
      <div className="mt-6 grid grid-cols-2 justify-items-center gap-x-3 gap-y-6 lg:grid-cols-4">
        {slots.map((s, i) => {
          const id = ids[i];
          const face = s.card && (
            <Link
              href={`/cards/${s.card.player_id}?week=${s.card.week}&as=${kind}&award=${s.award}`}
              className="block transition duration-200 hover:-translate-y-1"
              aria-label={`${s.title}: ${s.card.name}, ${s.card.overall}`}
            >
              <span className="sm:hidden">
                <PlayerCard card={s.card} size={0.64} />
              </span>
              <span className="hidden sm:block">
                <PlayerCard card={s.card} size={0.85} />
              </span>
            </Link>
          );
          const up = !faceDown || (id ? flipped.has(id) : true);
          return (
            <div key={s.award} className="flex flex-col items-center gap-2">
              <p className="font-display text-lg text-accent uppercase">
                {s.title}
              </p>
              {lockedNote ? (
                <LockedCard
                  title={s.title}
                  period={periodLabel}
                  note={lockedNote}
                />
              ) : s.card && id ? (
                faceDown ? (
                  <FlipCard
                    up={up}
                    animate={ready}
                    onFlip={() => flip(id)}
                    title={s.title}
                    period={periodLabel}
                  >
                    {face}
                  </FlipCard>
                ) : (
                  face
                )
              ) : (
                <p className="flex aspect-[5/7] w-[9.6em] items-center justify-center border border-dashed border-line p-3 text-center text-xs text-muted sm:w-[12.75em]">
                  {s.detail || "No winner yet"}
                </p>
              )}
              {s.card && (
                <p
                  className={`max-w-[12em] text-center text-xs text-muted transition-opacity duration-500 ${up ? "opacity-100" : "opacity-0"}`}
                  aria-hidden={!up}
                >
                  {s.detail}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}
