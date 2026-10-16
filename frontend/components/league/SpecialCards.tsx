"use client";

import Link from "next/link";
import { useState } from "react";

import {
  BLANK_PHOTO,
  runLabel,
  weekLabel,
  type CardSpecials,
  type IconRun,
  type PlayerCard as Card,
} from "@/lib/cards";
import { useApi } from "@/lib/useApi";

import AwardSlots from "./AwardSlots";
import Loading from "./Loading";
import PlayerCard from "./PlayerCard";

type View = "totw" | "rising" | "icons";

function intro(view: View, bars: CardSpecials["bars"]): string {
  if (view === "totw")
    return "The week's award winners: top player, rusher, sniper and grenader.";
  if (view === "rising")
    return `Up ${bars.rising_min} or more in overall since their last card: the three biggest jumps each week.`;
  return `Rated ${bars.icon_min} or more on ${bars.icon_weeks} cards in a row. An Icon keeps the card for as long as the run lasts.`;
}

/** Team of the Week, Rising Stars or Icons for a week, with a week picker. */
export default function SpecialCards({ view }: { view: View }) {
  const [week, setWeek] = useState<string | null>(null);
  const data = useApi<CardSpecials>(
    `/cards/specials${week ? `?week=${week}` : ""}`,
  );
  const d = data.data;

  if (!d) return <Loading error={data.error} count={4} />;
  if (!d.week && view !== "icons")
    return (
      <p className="text-muted">
        No cards yet. They come out every Saturday at midnight for the week
        before.
      </p>
    );
  return (
    <>
      {d.week && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="ml-auto flex items-center gap-2">
            <button
              className="btn px-3 py-1.5 text-sm"
              disabled={!d.previous}
              onClick={() => setWeek(d.previous)}
              aria-label="Earlier week"
            >
              &larr;
            </button>
            <span className="min-w-32 text-center font-display text-lg uppercase">
              {weekLabel(d.week)}
            </span>
            <button
              className="btn px-3 py-1.5 text-sm"
              disabled={!d.next}
              onClick={() => setWeek(d.next)}
              aria-label="Later week"
            >
              &rarr;
            </button>
          </span>
        </div>
      )}
      <p className="mt-3 text-sm text-muted">{intro(view, d.bars)}</p>

      {view === "totw" && d.week && (
        <AwardSlots
          kind="totw"
          period={d.week}
          periodLabel={`Week of ${weekLabel(d.week)}`}
          slots={d.team_of_week}
          faceDown={d.newest}
        />
      )}
      {view === "rising" && (
        <CardRow
          cards={d.rising}
          empty={`No Rising Stars this week: nobody went up ${d.bars.rising_min} or more.`}
          caption={(c) => (
            <span className="font-display text-2xl text-ok">
              +{c.rise} <span className="text-sm text-muted">overall</span>
            </span>
          )}
        />
      )}
      {view === "icons" && (
        <>
          <CardRow
            cards={d.icons}
            empty="No Icons this week."
            caption={(c) => (
              <span className="text-sm text-muted">
                <span className="font-display text-xl text-accent-2">
                  {c.streak}
                </span>{" "}
                weeks at {d.bars.icon_min}+
              </span>
            )}
          />
          <IconHall hall={d.hall} />
        </>
      )}
    </>
  );
}

function CardRow({
  cards,
  empty,
  caption,
}: {
  cards: Card[];
  empty: string;
  caption: (c: Card) => React.ReactNode;
}) {
  if (!cards.length) return <p className="mt-6 text-muted">{empty}</p>;
  return (
    <div className="mt-6 grid grid-cols-2 justify-items-center gap-x-3 gap-y-6 sm:grid-cols-3">
      {cards.map((c) => (
        <div key={c.player_id} className="flex flex-col items-center gap-2">
          <Link
            href={`/cards/${c.player_id}?week=${c.week}&as=${c.tier}`}
            className="transition duration-200 hover:-translate-y-1"
            aria-label={`${c.name}, ${c.overall}`}
          >
            <span className="sm:hidden">
              <PlayerCard card={c} size={0.64} />
            </span>
            <span className="hidden sm:block">
              <PlayerCard card={c} size={0.85} />
            </span>
          </Link>
          {caption(c)}
        </div>
      ))}
    </div>
  );
}

/** Every Icon run so far, the current ones first. */
function IconHall({ hall }: { hall: IconRun[] }) {
  return (
    <div className="mt-10">
      <h2 className="section-title">Hall of Icons</h2>
      {hall.length === 0 ? (
        <p className="mt-2 text-sm text-muted">
          Nobody yet. Who will be the first?
        </p>
      ) : (
        <ul className="mt-3 divide-y divide-line border border-line">
          {hall.map((r) => (
            <li
              key={`${r.player_id}-${r.from}`}
              className="flex items-center gap-3 px-3 py-2"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={r.photo || BLANK_PHOTO}
                alt=""
                className="h-10 w-10 bg-panel-2 object-cover object-top"
              />
              <Link
                href={`/cards/${r.player_id}`}
                className="font-semibold hover:text-accent"
              >
                {r.name}
              </Link>
              {r.current && (
                <span className="bg-accent-2 px-1.5 py-0.5 text-[0.65rem] font-bold text-bg uppercase">
                  Icon now
                </span>
              )}
              <span className="ml-auto text-right text-sm text-muted">
                {r.weeks} {r.weeks === 1 ? "week" : "weeks"} · best {r.best}
                <span className="block text-xs">{runLabel(r.from, r.to)}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
