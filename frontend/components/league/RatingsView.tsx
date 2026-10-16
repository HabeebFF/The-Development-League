"use client";

import { useState } from "react";

import { shortDate } from "@/lib/league";
import { ratingsPath, type DayRatings } from "@/lib/ratings";
import { useApi } from "@/lib/useApi";

import Loading from "./Loading";
import SearchBox from "./SearchBox";
import RatingTable, { StarPlayer } from "./RatingTable";

/** One day's player ratings (both sessions, or one), with arrows to other days. */
export default function RatingsView({ date = null, session = null }: { date?: string | null; session?: number | null }) {
  const [day, setDay] = useState<string | null>(date);
  const [sess, setSess] = useState<number | null>(session);
  const [query, setQuery] = useState("");
  const data = useApi<DayRatings>(ratingsPath(day, sess));
  const r = data.data;

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <button className={`btn px-4 py-1.5 text-sm uppercase ${sess == null ? "btn-primary" : ""}`} onClick={() => setSess(null)}>
          Day
        </button>
        {r?.sessions.map((s) => (
          <button
            key={s.id}
            className={`btn px-4 py-1.5 text-sm uppercase ${sess === s.id ? "btn-primary" : ""}`}
            onClick={() => {
              setDay(r.date);
              setSess(s.id);
            }}
          >
            {sessionName(s.title)}
          </button>
        ))}
        {r && (
          <span className="flex w-full items-center gap-2 sm:ml-auto sm:w-auto">
            <button
              className="btn px-3 py-1.5 text-sm"
              disabled={!r.previous}
              onClick={() => {
                setDay(r.previous);
                setSess(null);
              }}
              aria-label="Earlier day"
            >
              &larr;
            </button>
            <span className="min-w-36 flex-1 truncate text-center font-display text-lg uppercase">{r.date ? shortDate(r.date) : "No days yet"}</span>
            <button
              className="btn px-3 py-1.5 text-sm"
              disabled={!r.next}
              onClick={() => {
                setDay(r.next);
                setSess(null);
              }}
              aria-label="Later day"
            >
              &rarr;
            </button>
          </span>
        )}
      </div>

      <div className="mt-4">
        <SearchBox value={query} onChange={setQuery} />
      </div>

      {!r ? (
        <div className="mt-6">
          <Loading error={data.error} count={10} />
        </div>
      ) : r.matches === 0 ? (
        <p className="mt-6 text-sm text-muted">No rated matches {r.date ? "on this day" : "yet"}.</p>
      ) : (
        <div className="mt-6 space-y-6">
          {r.star != null && !query.trim() && (
            <StarPlayer
              row={r.players.find((p) => p.player_id === r.star)!}
              label={r.session ? "Player of the session" : "Player of the Day"}
            />
          )}
          <RatingTable board={r} query={query} />
        </div>
      )}

      <details className="mt-10 text-sm text-muted">
        <summary className="cursor-pointer font-semibold text-text">How ratings work</summary>
        <p className="mt-2">
          Like the football apps, every player starts a match on 5.7. Kills, knocks, headshots, opening fights and trades add to it. The team&apos;s place
          (a Booyah is worth a full point) and how long they stayed alive move it up or down, and getting knocked alone or being the team&apos;s first
          player down takes a little off. Ratings run from 3.0 to 10.0; a normal match is about 6.5 and 8.0 or better is a big game. A day&apos;s rating is
          the average of the player&apos;s matches that day. Open any match to see how each rating was made.
        </p>
      </details>
    </>
  );
}

/** "TDL DAY 19 8PM" -> "8PM"; a title with no time stays whole. */
function sessionName(title: string): string {
  const m = title.match(/\b(\d{1,2}(?::\d{2})?\s?[AP]M)\b/i);
  return m ? m[1].toUpperCase().replace(/\s/g, "") : title;
}
