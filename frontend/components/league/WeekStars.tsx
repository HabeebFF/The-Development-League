"use client";

import Link from "next/link";

import { asSpecial, weekLabel, type CardSpecials } from "@/lib/cards";
import { useApi } from "@/lib/useApi";

import PlayerCard from "./PlayerCard";

/** The latest revealed Team of the Week (top player, rusher, sniper, grenader), with a way into /cards. */
export default function WeekStars() {
  const data = useApi<CardSpecials>("/cards/specials");
  const d = data.data;
  const slots = d?.team_of_week.filter((s) => s.card) ?? [];
  if (!d?.week || !slots.length) return null;
  return (
    <div className="mt-8 border-t border-line pt-6 sm:mt-12 sm:pt-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow text-accent-2">★ Team of the Week</p>
          <p className="mt-1 font-display text-2xl uppercase sm:text-3xl">Week of {weekLabel(d.week)}</p>
        </div>
        <span className="hidden sm:block">
          <Link href="/cards" className="btn btn-primary px-5 py-2.5 text-sm">
            See all player cards &rarr;
          </Link>
        </span>
      </div>
      <div className="mt-6 grid grid-cols-2 justify-items-center gap-x-3 gap-y-6 lg:grid-cols-4">
        {slots.map((s) => {
          const card = asSpecial(s.card!, "totw");
          return (
            <Link
              key={s.award}
              href={`/cards/${card.player_id}?week=${card.week}&as=totw&award=${s.award}`}
              className="group flex flex-col items-center gap-2 transition-transform hover:-translate-y-1"
            >
              <span className="text-[11px] font-bold tracking-widest text-muted uppercase group-hover:text-accent">{s.title}</span>
              <span className="sm:hidden">
                <PlayerCard card={card} size={0.6} />
              </span>
              <span className="hidden sm:block">
                <PlayerCard card={card} size={0.8} />
              </span>
            </Link>
          );
        })}
      </div>
      <div className="mt-6 sm:hidden">
        <Link href="/cards" className="btn btn-primary w-full justify-center px-5 py-3 text-base">
          See all player cards &rarr;
        </Link>
      </div>
    </div>
  );
}
