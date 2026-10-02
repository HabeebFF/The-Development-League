"use client";

import type { MatchDay, Paged } from "@/lib/api";
import { currentSeason, playedNewestFirst, rows, type Season } from "@/lib/league";
import { useApi } from "@/lib/useApi";

import Loading from "./Loading";
import MatchDayCard from "./MatchDayCard";

/** The current season's played match days, newest first. */
export default function ResultsView() {
  const seasons = useApi<Paged<Season>>("/seasons?page_size=100");
  const season = seasons.data ? currentSeason(rows(seasons.data)) : null;
  const days = useApi<Paged<MatchDay>>(season && `/match-days?season=${encodeURIComponent(season.slug)}&page_size=100`);

  if (seasons.data && !season) return <p className="text-muted">The first season hasn&apos;t started yet.</p>;
  if (!days.data) return <Loading error={seasons.error ?? days.error} />;
  const played = playedNewestFirst(rows(days.data));
  if (!played.length) return <p className="text-muted">No matches played yet.</p>;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {played.map((d) => (
        <MatchDayCard key={d.id} day={d} />
      ))}
    </div>
  );
}
