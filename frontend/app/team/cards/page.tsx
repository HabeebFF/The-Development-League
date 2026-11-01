"use client";

import { useEffect, useState } from "react";

import DayCards from "@/components/team/DayCards";
import { api, type Paged, type TeamRef } from "@/lib/api";

import { useTeam } from "../TeamGate";

/** Daily player cards for the signed-in member's own team (staff pick a team). */
export default function TeamDayCardsPage() {
  const { membership } = useTeam();
  const [teams, setTeams] = useState<TeamRef[] | null>(null);
  const [picked, setPicked] = useState("");

  useEffect(() => {
    if (membership) return;
    api<Paged<TeamRef>>("/teams?page_size=100")
      .then((p) => setTeams(p.results))
      .catch(() => setTeams([]));
  }, [membership]);

  const slug = membership?.team.slug ?? picked;
  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <p className="text-sm font-semibold tracking-[0.2em] text-accent uppercase">
        Daily cards
      </p>
      <h1 className="mt-1 font-display text-5xl leading-none font-extrabold uppercase">
        {membership?.team.name ?? "Every team"}
      </h1>
      <p className="mt-2 text-sm text-muted">
        Each player&apos;s card for one match day. Only your team can see these.
      </p>
      {!membership && (
        <select
          className="input mt-4 sm:max-w-xs"
          value={picked}
          onChange={(e) => setPicked(e.target.value)}
          aria-label="Team"
        >
          <option value="">Pick a team</option>
          {(teams ?? []).map((t) => (
            <option key={t.slug} value={t.slug}>
              {t.name}
            </option>
          ))}
        </select>
      )}
      <div className="mt-6">{slug && <DayCards key={slug} slug={slug} />}</div>
    </section>
  );
}
