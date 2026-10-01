"use client";

import { useState } from "react";

import type { MatchDay, Paged } from "@/lib/api";
import { currentSeason, dayName, rows, shortDate, type Season, type SeasonDetail, type Standings } from "@/lib/league";
import { useApi } from "@/lib/useApi";

import Loading from "./Loading";
import StandingsTable from "./StandingsTable";

/** The full table, for the season or one stage, group or match day. */
export default function StandingsView() {
  const seasons = useApi<Paged<Season>>("/seasons?page_size=100");
  const all = seasons.data ? rows(seasons.data) : [];
  const [picked, setPicked] = useState<string | null>(null);
  const slug = picked ?? currentSeason(all)?.slug ?? null;
  const [scope, setScope] = useState(""); // "", "stage=1", "group=2" or "match_day=3"

  const enc = slug ? encodeURIComponent(slug) : null;
  const detail = useApi<SeasonDetail>(enc && `/seasons/${enc}`);
  const days = useApi<Paged<MatchDay>>(enc && `/match-days?season=${enc}&page_size=100`);
  const table = useApi<Standings>(enc && `/seasons/${enc}/standings${scope ? `?${scope}` : ""}`);

  if (!seasons.data) return <Loading error={seasons.error} />;
  if (!slug) return <p className="text-muted">The first season hasn&apos;t started yet.</p>;

  const played = (days.data ? rows(days.data) : []).filter((d) => d.matches.some((m) => m.played));
  const stages = detail.data?.stages ?? [];

  return (
    <>
      <div className="flex flex-col gap-2 sm:flex-row">
        {all.length > 1 && (
          <select
            className="input sm:w-56"
            value={slug}
            onChange={(e) => {
              setPicked(e.target.value);
              setScope("");
            }}
          >
            {all.map((s) => (
              <option key={s.slug} value={s.slug}>
                {s.name}
              </option>
            ))}
          </select>
        )}
        <select className="input sm:w-72" value={scope} onChange={(e) => setScope(e.target.value)}>
          <option value="">Whole season</option>
          {stages.length > 1 &&
            stages.map((st) => (
              <option key={`s${st.id}`} value={`stage=${st.id}`}>
                {st.name}
              </option>
            ))}
          {stages.flatMap((st) =>
            st.groups.map((g) => (
              <option key={`g${g.id}`} value={`group=${g.id}`}>
                {stages.length > 1 ? `${st.name} · ` : ""}
                {g.name}
              </option>
            )),
          )}
          {played.length > 0 && (
            <optgroup label="Match days">
              {[...played].reverse().map((d) => (
                <option key={`d${d.id}`} value={`match_day=${d.id}`}>
                  {dayName(d)}
                  {d.date ? ` · ${shortDate(d.date)}` : ""}
                </option>
              ))}
            </optgroup>
          )}
        </select>
      </div>

      <div className="mt-4">{table.data ? <StandingsTable rows={table.data.rows} /> : <Loading error={table.error} />}</div>
      {detail.data?.scoring && (
        <p className="mt-3 text-xs text-muted">
          Points: {detail.data.scoring.name}, {detail.data.scoring.points_per_kill} per kill.
          {table.data?.updated_at ? ` Updated ${shortDate(table.data.updated_at)}.` : ""}
        </p>
      )}
    </>
  );
}
