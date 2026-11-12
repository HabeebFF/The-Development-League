"use client";

import Link from "next/link";

import EmptyState from "@/components/ui/EmptyState";
import RankBadge from "@/components/ui/RankBadge";
import type { Paged } from "@/lib/api";
import { currentSeason, rows, type Season, type Standings, type Team } from "@/lib/league";
import { useApi } from "@/lib/useApi";

import { Skeleton } from "./Loading";
import { TeamMark } from "./TeamBadge";

/** Every league team as a card: crest, name, tag and where it sits in the current season's table. */
export default function TeamsView() {
  const teams = useApi<Paged<Team>>("/teams?page_size=100");
  // The overall table, for each team's current rank and points (the same reads Standings makes).
  const seasons = useApi<Paged<Season>>("/seasons?page_size=100");
  const season = seasons.data ? currentSeason(rows(seasons.data)) : null;
  const table = useApi<Standings>(season && `/seasons/${encodeURIComponent(season.slug)}/standings`);
  const standing = new Map((table.data?.rows ?? []).map((r) => [r.team.id, r]));

  if (teams.error) return <p className="text-down" role="alert">{teams.error}</p>;
  if (!teams.data)
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} className="h-52" />
        ))}
      </div>
    );
  const all = rows(teams.data).sort((a, b) => a.name.localeCompare(b.name));
  if (!all.length) return <EmptyState title="No teams yet">Teams show up here once staff add them.</EmptyState>;
  return (
    <ul className="stagger grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {all.map((t) => {
        const s = standing.get(t.id);
        const colour = t.primary_color || "var(--accent)";
        return (
          <li key={t.id}>
            <Link href={`/teams/${t.slug}`} className="card card-hover group relative flex h-full flex-col items-center gap-3 overflow-hidden p-4 pt-6 text-center sm:p-5 sm:pt-7">
              <span
                className="pointer-events-none absolute inset-x-0 top-0 h-24 opacity-40 transition-opacity group-hover:opacity-70"
                style={{ background: `linear-gradient(180deg, ${colour}, transparent)` }}
              />
              <span className="pointer-events-none absolute inset-x-0 top-0 h-1" style={{ background: colour }} />
              {s && (
                <span className="absolute top-2 left-2 scale-75 origin-top-left" title={`${s.rank} in the table`}>
                  <RankBadge rank={s.rank} />
                </span>
              )}
              <span className="relative transition-transform duration-300 group-hover:scale-105">
                <TeamMark team={t} size="lg" />
              </span>
              <span className="relative w-full truncate font-display text-xl leading-tight font-extrabold uppercase">{t.name}</span>
              {t.tag && <span className="relative -mt-2 text-xs font-semibold tracking-widest text-muted uppercase">{t.tag}</span>}
              {s && (
                <span className="relative mt-auto flex w-full justify-around border-t border-line pt-2.5">
                  <span>
                    <span className="num block text-xl leading-none text-accent-hot">{s.total_points}</span>
                    <span className="text-[9px] font-bold tracking-[0.14em] text-muted uppercase">Pts</span>
                  </span>
                  <span>
                    <span className="num block text-xl leading-none">{s.booyahs}</span>
                    <span className="text-[9px] font-bold tracking-[0.14em] text-muted uppercase">Booyahs</span>
                  </span>
                  <span>
                    <span className="num block text-xl leading-none">{s.kills}</span>
                    <span className="text-[9px] font-bold tracking-[0.14em] text-muted uppercase">Kills</span>
                  </span>
                </span>
              )}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
