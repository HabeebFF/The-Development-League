"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, type MatchDay, type Paged } from "@/lib/api";

import { useTeam } from "./TeamGate";

export default function TeamHome() {
  const { me, membership } = useTeam();
  const [days, setDays] = useState<MatchDay[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Paged<MatchDay>>("/match-days?page_size=100")
      .then((page) => setDays([...page.results].reverse()))
      .catch((e) => setError(e.message));
  }, []);

  const played = (days ?? []).filter((d) => d.matches.some((m) => m.played));
  const canStudy = me.features.includes("rotations.view");

  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <p className="text-sm font-semibold tracking-[0.2em] text-accent uppercase">
        {membership ? (membership.role === "MANAGER" ? "Team manager" : "Team player") : "League staff"}
      </p>
      <h1 className="mt-1 font-display text-4xl uppercase">{membership?.team.name ?? "Team area"}</h1>
      <p className="mt-2 text-sm text-muted">Signed in as {me.email}</p>
      {membership && (
        <Link href="/team/members" className="btn mt-4 inline-block">
          {membership.role === "MANAGER" ? "Members and invites" : "Team members"}
        </Link>
      )}

      <h2 className="mt-10 font-display text-2xl uppercase">Matches</h2>
      {!canStudy && (
        <p className="mt-2 text-sm text-muted">
          Live replays and rotations are for league teams. Ask league staff if your team should have them.
        </p>
      )}
      {error && <p className="mt-4 text-bad">{error}</p>}
      {!days && !error && <p className="mt-4 text-muted">Loading...</p>}
      {days && played.length === 0 && <p className="mt-4 text-muted">No matches have been played yet.</p>}
      <div className="mt-4 space-y-6">
        {played.map((day) => (
          <div key={day.id}>
            <h3 className="text-sm font-semibold text-muted uppercase">
              {day.title || `Day ${day.number}`}
              {day.date ? ` · ${new Date(day.date).toLocaleDateString()}` : ""}
            </h3>
            <ul className="mt-2 divide-y divide-line rounded-lg border border-line bg-panel">
              {day.matches
                .filter((m) => m.played)
                .map((m) => (
                  <li key={m.id} className="flex flex-wrap items-center gap-2 px-4 py-3">
                    <span className="flex-1">
                      <span className="block font-medium">Match {m.number}</span>
                      <span className="text-xs text-muted uppercase">
                        {m.map ?? "No map"}
                        {m.booyah ? ` · Booyah: ${m.booyah.name}` : ""}
                      </span>
                    </span>
                    {canStudy && (
                      <>
                        <Link href={`/team/matches/${m.id}/replay`} className="btn px-3 py-1 text-sm">
                          Live replay
                        </Link>
                        <Link href={`/team/matches/${m.id}/rotations`} className="btn px-3 py-1 text-sm">
                          Rotations
                        </Link>
                      </>
                    )}
                  </li>
                ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
