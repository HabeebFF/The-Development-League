"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { finishText, MOMENT_LABELS, repeatedMistakes, type ReviewMatch, type TeamReview } from "@/lib/coach";
import { replayHref } from "@/lib/replay";

/** After a scrim session: each match's moments that cost the team, with a link into the replay. */
export default function ScrimReview({ teamSlug, replayBase }: { teamSlug: string; replayBase: (id: number) => string }) {
  const [review, setReview] = useState<TeamReview | null>(null);
  const [day, setDay] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const query = day ? `?day=${day}` : "";
    api<TeamReview>(`/coach/teams/${teamSlug}/review${query}`)
      .then((r) => {
        setReview(r);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't load the review."));
  }, [teamSlug, day]);

  if (error) return <p className="text-bad">{error}</p>;
  if (!review) return <p className="text-muted">Loading...</p>;
  if (!review.day) return <p className="text-muted">Your review appears here after your first match is uploaded.</p>;

  const repeated = repeatedMistakes(review.matches);
  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <select
          className="input max-w-xs"
          value={review.day.id}
          onChange={(e) => setDay(Number(e.target.value))}
          aria-label="Match day"
        >
          {review.days.map((d) => (
            <option key={d.id} value={d.id}>
              {d.label}
              {d.date ? ` · ${d.date}` : ""}
            </option>
          ))}
        </select>
        <p className="text-sm text-muted">The moments that cost you most in each match, and your best one.</p>
      </div>

      {repeated.length > 0 && (
        <div className="card mt-4 border-l-2 border-l-accent p-4">
          <p className="eyebrow">Came back more than once</p>
          <ul className="mt-2 flex flex-wrap gap-2 text-sm">
            {repeated.map((r) => (
              <li key={r.kind} className="chip">
                {r.label} · {r.matches} matches
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-4 space-y-4">
        {review.matches.map((m) => (
          <MatchCard key={m.id} match={m} replay={replayBase(m.id)} teamSlug={teamSlug} />
        ))}
      </div>
    </div>
  );
}

function MatchCard({ match, replay, teamSlug }: { match: ReviewMatch; replay: string; teamSlug: string }) {
  return (
    <section className="card p-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-display text-2xl uppercase">
          {match.label}
          {match.map ? <span className="text-muted"> · {match.map}</span> : null}
        </h3>
        <p className={`text-sm ${match.placement === 1 ? "font-semibold text-accent" : "text-muted"}`}>
          {finishText(match)} · {match.kills} kills
        </p>
      </header>
      {match.moments.length === 0 ? (
        <p className="mt-3 text-sm text-muted">Nothing stood out in this match.</p>
      ) : (
        <ol className="mt-3 space-y-3">
          {match.moments.map((x) => (
            <li key={`${x.kind}-${x.t}`} className="flex gap-3">
              <span className="w-12 shrink-0 pt-0.5 font-display text-lg leading-none text-muted tabular-nums">{x.clock}</span>
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 font-medium">
                  <span className={`chip ${x.good ? "text-ok" : "text-bad"}`}>{MOMENT_LABELS[x.kind] ?? x.kind}</span>
                  <span>{x.title}</span>
                </p>
                <p className="mt-1 text-sm text-muted">{x.detail}</p>
                {match.has_tracks && (
                  // A wrapper shows or hides it: .btn sets its own display.
                  <div className="mt-2 sm:hidden">
                    <Link href={replayHref(replay, x.watch_s, teamSlug)} className="btn text-sm">
                      Watch this
                    </Link>
                  </div>
                )}
              </div>
              {match.has_tracks && (
                <div className="hidden shrink-0 self-start sm:block">
                  <Link href={replayHref(replay, x.watch_s, teamSlug)} className="btn text-sm">
                    Watch this
                  </Link>
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
