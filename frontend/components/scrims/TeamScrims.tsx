"use client";

import { useCallback, useEffect, useState } from "react";

import TeamBadge from "@/components/league/TeamBadge";
import { api } from "@/lib/api";
import { action, clock, myStatus, nightName, places, stageText, type ScrimSession, type TeamNight } from "@/lib/scrims";

/** The team page's "Scrims" card: sign up for 8PM and 10PM, or withdraw (managers only). */
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

  async function press(s: ScrimSession, what: "register" | "withdraw") {
    setBusy(s.session);
    setError(null);
    try {
      setNight(await api<TeamNight>(`/teams/${slug}/scrims/${s.date}/${s.session}/${what}`, { method: "POST" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work. Try again.");
      load();
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="mt-10">
      <h2 className="font-display text-2xl uppercase">Scrims{night?.date ? ` · ${nightName(night.date)}` : ""}</h2>
      <p className="mt-1 text-sm text-muted">
        Monday, Tuesday, Thursday and Friday. Sign-up for 8PM and 10PM opens at 12:01pm on the day.
        {night && !night.can_manage && " Your team's managers sign the team up."}
      </p>
      {night?.suspended && (
        <div className="mt-4 card border-l-4 border-bad p-4">
          <p className="font-semibold text-bad">Your team is suspended and can&apos;t sign up for scrims.</p>
          {night.suspended.reason && <p className="mt-1 text-sm">Reason: {night.suspended.reason}</p>}
          <p className="mt-1 text-sm text-muted">
            {night.suspended.until ? `Until ${night.suspended.until}.` : "Until league staff lift it."}
          </p>
        </div>
      )}
      {error && <p className="mt-3 text-bad">{error}</p>}
      {!night && !error && <p className="mt-4 text-muted">Loading...</p>}
      {night && !night.date && <p className="mt-4 text-muted">No scrims are planned in the next two weeks.</p>}
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {night?.sessions.map((s) => {
          const button = action(s, night.can_manage, !!night.suspended);
          const { taken, left } = places(s);
          const mine = s.mine === "REGISTERED" ? "text-ok" : s.mine === "WAITLIST" ? "text-accent" : "text-muted";
          return (
            <div key={s.session} className="card p-4 sm:p-5">
              <div className="flex items-baseline justify-between gap-3">
                <h3 className="font-display text-3xl leading-none font-black uppercase">{s.session}</h3>
                <span className="num text-2xl leading-none">
                  {taken}
                  <span className="ml-1 text-xs tracking-[0.14em] text-muted">TEAMS</span>
                </span>
              </div>
              <p className="mt-1 text-sm text-muted">{stageText(s)}</p>
              <p className={`mt-3 font-display text-xl font-bold uppercase ${mine}`}>{myStatus(s)}</p>
              {s.stage === "open" && !s.mine && (
                <p className="text-xs text-muted">{left > 0 ? `${left} place${left === 1 ? "" : "s"} left` : "Full: you'd join the waitlist"}</p>
              )}
              {button && (
                <button
                  type="button"
                  className={`btn mt-3 w-full ${button === "register" ? "btn-primary" : ""}`}
                  disabled={busy === s.session}
                  onClick={() => press(s, button)}
                >
                  {busy === s.session ? "Saving..." : button === "register" ? `Sign up for ${s.session}` : "Withdraw"}
                </button>
              )}
              {s.stage === "soon" && night.can_manage && !night.suspended && (
                <p className="mt-3 text-xs text-muted">Come back at {clock(s.opens_at)} to sign up.</p>
              )}
              {s.playing.length > 0 && (
                <details className="mt-3 text-sm">
                  <summary className="cursor-pointer text-muted">Teams playing</summary>
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
    </section>
  );
}
