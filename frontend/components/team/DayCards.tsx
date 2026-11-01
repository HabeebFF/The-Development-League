"use client";

import { useState } from "react";

import Loading from "@/components/league/Loading";
import PlayerCard from "@/components/league/PlayerCard";
import RatingBadge from "@/components/league/RatingBadge";
import {
  changeText,
  type DayCard,
  type PlayerCard as Card,
  type TeamDayCards,
} from "@/lib/cards";
import { useApi } from "@/lib/useApi";

/** "Sat 31 Oct". */
export function dayText(iso: string, long = false): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", {
    weekday: long ? "long" : "short",
    day: "numeric",
    month: long ? "long" : "short",
  });
}

/** One team's daily player cards, with a day picker. Tap a card for the numbers behind it. */
export default function DayCards({ slug }: { slug: string }) {
  const [day, setDay] = useState<string | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const data = useApi<TeamDayCards>(
    `/teams/${slug}/day-cards${day ? `?date=${day}` : ""}`,
  );
  const d = data.data;
  const pick = (next: string | null) => {
    if (!next) return;
    setDay(next);
    setOpen(null);
  };
  const chosen = d?.cards.find((c) => c.player_id === open) ?? null;

  if (!d) return <Loading error={data.error} count={4} />;
  if (!d.date) {
    return (
      <p className="text-muted">
        No daily cards yet. They show up after your team&apos;s matches are
        uploaded.
      </p>
    );
  }
  return (
    <>
      <div className="flex items-center gap-2">
        <button
          className="btn px-3 py-1.5 text-sm"
          disabled={!d.previous}
          onClick={() => pick(d.previous)}
          aria-label="Earlier day"
        >
          &larr;
        </button>
        <select
          className="input font-display text-lg uppercase"
          style={{ width: "auto" }}
          value={d.date}
          onChange={(e) => pick(e.target.value)}
          aria-label="Match day"
        >
          {d.days.map((x) => (
            <option key={x} value={x}>
              {dayText(x)}
            </option>
          ))}
        </select>
        <button
          className="btn px-3 py-1.5 text-sm"
          disabled={!d.next}
          onClick={() => pick(d.next)}
          aria-label="Later day"
        >
          &rarr;
        </button>
      </div>
      <p className="mt-3 text-sm text-muted">
        {dayText(d.date, true)}. Each card is made from that day&apos;s matches
        only, and every stat compares the player with everyone who played that
        day. The small number under the overall is the gap to their weekly card.
      </p>

      {d.cards.length === 0 ? (
        <p className="mt-6 text-muted">
          Nobody on the team played {d.need} matches that day.
        </p>
      ) : (
        <div className="mt-6 grid grid-cols-2 justify-items-center gap-x-3 gap-y-5 sm:grid-cols-3 lg:grid-cols-5">
          {d.cards.map((c) => (
            <button
              key={c.player_id}
              type="button"
              onClick={() => setOpen(open === c.player_id ? null : c.player_id)}
              className={`flex flex-col items-center transition duration-200 hover:-translate-y-1 ${open === c.player_id ? "-translate-y-1" : ""}`}
              aria-expanded={open === c.player_id}
              aria-label={`${c.name}, ${c.overall} ${c.role_label} on ${dayText(d.date!)}`}
            >
              <span className="sm:hidden">
                <PlayerCard
                  card={c as Card}
                  size={0.64}
                  footer={`Daily · ${dayText(c.day)}`}
                />
              </span>
              <span className="hidden sm:block">
                <PlayerCard
                  card={c as Card}
                  size={0.78}
                  footer={`Daily · ${dayText(c.day)}`}
                />
              </span>
              <DayLine card={c} />
            </button>
          ))}
        </div>
      )}

      {chosen && <Detail card={chosen} onClose={() => setOpen(null)} />}

      {d.short.length > 0 && (
        <div className="mt-8">
          <h2 className="font-display text-xl uppercase">
            Not enough matches for a card
          </h2>
          <p className="text-sm text-muted">
            A daily card needs {d.need} matches that day.
          </p>
          <ul className="mt-2 divide-y divide-line card">
            {d.short.map((c) => (
              <li
                key={c.player_id}
                className="flex items-center gap-3 px-4 py-2"
              >
                <span className="flex-1 font-medium">{c.name}</span>
                <span className="text-sm text-muted">
                  {c.matches} {c.matches === 1 ? "match" : "matches"} ·{" "}
                  {c.kills} {c.kills === 1 ? "kill" : "kills"}
                </span>
                {c.rating !== null && c.rating_band && (
                  <RatingBadge
                    rating={c.rating}
                    band={c.rating_band}
                    size="sm"
                  />
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

/** Under each card: the day's rating, kills and matches. */
function DayLine({ card }: { card: DayCard }) {
  return (
    <span className="mt-1 flex items-center gap-2 text-xs text-muted">
      {card.rating !== null && card.rating_band && (
        <RatingBadge rating={card.rating} band={card.rating_band} size="sm" />
      )}
      <span>
        {card.kills} {card.kills === 1 ? "kill" : "kills"} · {card.matches}{" "}
        matches
      </span>
    </span>
  );
}

function Detail({ card, onClose }: { card: DayCard; onClose: () => void }) {
  return (
    <div className="mt-6 card p-4 sm:p-5">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="font-display text-2xl uppercase">{card.name}</h2>
        <span className="text-sm text-muted">
          {card.role_label} · {dayText(card.day, true)}
        </span>
        <button
          className="ml-auto text-sm text-muted hover:text-text"
          onClick={onClose}
        >
          Close
        </button>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-5">
        <Fact label="Overall" value={String(card.overall ?? "-")} />
        <Fact
          label="Weekly card"
          value={
            card.weekly_overall !== null
              ? `${card.weekly_overall}${card.overall_change ? ` (${changeText(card.overall_change)})` : ""}`
              : "None yet"
          }
        />
        <Fact
          label="Rating"
          value={card.rating !== null ? card.rating.toFixed(1) : "-"}
        />
        <Fact label="Kills / knocks" value={`${card.kills} / ${card.knocks}`} />
        <Fact
          label="Damage"
          value={
            card.damage !== null ? card.damage.toLocaleString() : "Not logged"
          }
        />
      </dl>
      <ul className="mt-4 divide-y divide-line">
        {card.stats.map((s) => (
          <li key={s.key} className="flex items-baseline gap-3 py-2">
            <span className="w-8 text-right font-display text-xl tabular-nums">
              {s.rating ?? "–"}
            </span>
            <span className="w-28 shrink-0 font-display uppercase">
              {s.label}
            </span>
            <span className="text-sm text-muted">{s.detail}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted uppercase">{label}</dt>
      <dd className="font-display text-lg">{value}</dd>
    </div>
  );
}
