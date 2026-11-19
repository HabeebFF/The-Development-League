"use client";

import { useCallback, useEffect, useState } from "react";

import TeamBadge from "@/components/league/TeamBadge";
import { api } from "@/lib/api";
import {
  actionLabel,
  actions,
  dayClock,
  dc,
  endpoint,
  myStatus,
  nightName,
  places,
  stageText,
  type Action,
  type ScrimSession,
  type TeamNight,
} from "@/lib/scrims";

/** The team page's "Scrims" card: sign up for 8PM and 10PM (paying the DC fee), confirm a staff
 * invite, or withdraw. Managers and players with a linked game UID. Tonight and the next night. */
export default function TeamScrims({ slug }: { slug: string }) {
  const [night, setNight] = useState<TeamNight | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    api<TeamNight>(`/teams/${slug}/scrims`)
      .then((d) => {
        setNight(d);
        setError(null);
      })
      .catch((e) => setError(e.message));
  }, [slug]);

  useEffect(() => {
    load();
    // Keep places and stage fresh while the page is open.
    const timer = setInterval(load, 60_000);
    return () => clearInterval(timer);
  }, [load]);

  async function press(s: ScrimSession, what: Action) {
    const id = `${s.date}-${s.session}`;
    setBusy(id);
    setError(null);
    try {
      setNight(
        await api<TeamNight>(
          `/teams/${slug}/scrims/${s.date}/${s.session}/${endpoint(what)}`,
          { method: "POST" },
        ),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work. Try again.");
      load();
    } finally {
      setBusy(null);
    }
  }

  const fee = night?.fee ?? 0;
  return (
    <section className="mt-10">
      <h2 className="font-display text-2xl uppercase">Scrims</h2>
      <p className="mt-1 text-sm text-muted">
        Monday, Tuesday, Thursday and Friday. Sign-up for 8PM and 10PM opens at
        8:00pm the night before
        {fee > 0
          ? ` and costs ${dc(fee)} a session, paid by whoever signs the team up (refunded if you withdraw)`
          : ""}
        . When a session is full, predictions open and only staff can take a
        team out.
        {night &&
          !night.can_manage &&
          " Your team's managers and players with a linked game UID sign the team up."}
      </p>
      {night?.suspended && (
        <div className="mt-4 card border-l-4 border-bad p-4">
          <p className="font-semibold text-bad">
            Your team is suspended and can&apos;t sign up for scrims.
          </p>
          {night.suspended.reason && (
            <p className="mt-1 text-sm">Reason: {night.suspended.reason}</p>
          )}
          <p className="mt-1 text-sm text-muted">
            {night.suspended.until
              ? `Until ${night.suspended.until}.`
              : "Until league staff lift it."}
          </p>
        </div>
      )}
      {error && <p className="mt-3 text-bad">{error}</p>}
      {!night && !error && <p className="mt-4 text-muted">Loading...</p>}
      {night && night.nights.length === 0 && (
        <p className="mt-4 text-muted">
          No scrims are planned in the next two weeks.
        </p>
      )}
      {night?.nights.map((n) => (
        <div key={n.date} className="mt-5">
          <h3 className="font-display text-lg uppercase text-muted">
            {n.date ? nightName(n.date) : ""}
          </h3>
          <div className="mt-2 grid gap-4 md:grid-cols-2">
            {n.sessions.map((s) => {
              const id = `${s.date}-${s.session}`;
              const buttons = actions(s, night.can_manage, !!night.suspended);
              const { taken, left } = places(s);
              const mine =
                s.mine === "REGISTERED"
                  ? "text-ok"
                  : s.mine === "INVITED" || s.mine === "WAITLIST"
                    ? "text-accent"
                    : "text-muted";
              return (
                <div key={id} className="card p-4 sm:p-5">
                  <div className="flex items-baseline justify-between gap-3">
                    <h4 className="font-display text-3xl leading-none font-black uppercase">
                      {s.session}
                    </h4>
                    <span className="num text-2xl leading-none">
                      {taken}
                      <span className="ml-1 text-xs tracking-[0.14em] text-muted">
                        TEAMS
                      </span>
                    </span>
                  </div>
                  <p
                    className={`mt-1 text-sm ${s.locked ? "text-accent" : "text-muted"}`}
                  >
                    {stageText(s)}
                  </p>
                  <p
                    className={`mt-3 font-display text-xl font-bold uppercase ${mine}`}
                  >
                    {myStatus(s)}
                  </p>
                  {s.stage === "open" && !s.mine && !s.locked && (
                    <p className="text-xs text-muted">
                      {left > 0
                        ? `${left} place${left === 1 ? "" : "s"} left`
                        : "Full: you'd join the waitlist"}
                    </p>
                  )}
                  {s.mine === "REGISTERED" &&
                    s.locked &&
                    s.stage === "open" && (
                      <p className="text-xs text-muted">
                        The session is full. Ask staff if you can&apos;t play.
                      </p>
                    )}
                  {buttons.length > 0 && (
                    <div className="mt-3 flex gap-2">
                      {buttons.map((b, i) => (
                        <button
                          key={b}
                          type="button"
                          className={`btn ${i === 0 ? "flex-1" : ""} ${b === "register" || b === "confirm" ? "btn-primary" : ""}`}
                          disabled={busy === id}
                          onClick={() => press(s, b)}
                        >
                          {busy === id ? "Saving..." : actionLabel(b, s)}
                        </button>
                      ))}
                    </div>
                  )}
                  {s.stage === "soon" &&
                    night.can_manage &&
                    !night.suspended &&
                    s.mine !== "INVITED" && (
                      <p className="mt-3 text-xs text-muted">
                        Come back {dayClock(s.opens_at)} to sign up.
                      </p>
                    )}
                  {s.playing.length > 0 && (
                    <details className="mt-3 text-sm">
                      <summary className="cursor-pointer text-muted">
                        Teams playing
                      </summary>
                      <ol className="mt-2 space-y-1.5">
                        {s.playing.map((e) => (
                          <li key={e.team.id}>
                            <TeamBadge team={e.team} />
                          </li>
                        ))}
                      </ol>
                    </details>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </section>
  );
}
