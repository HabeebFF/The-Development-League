"use client";

import Link from "next/link";

import type { Paged } from "@/lib/api";
import { rows, type Team } from "@/lib/league";
import { useApi } from "@/lib/useApi";

import { Skeleton } from "./Loading";
import { TeamMark } from "./TeamBadge";

/** Every league team. */
export default function TeamsView() {
  const teams = useApi<Paged<Team>>("/teams?page_size=100");
  if (teams.error) return <p className="text-bad">{teams.error}</p>;
  if (!teams.data)
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} className="h-44" />
        ))}
      </div>
    );
  const all = rows(teams.data).sort((a, b) => a.name.localeCompare(b.name));
  if (!all.length) return <p className="text-muted">No teams yet.</p>;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {all.map((t) => (
        <Link key={t.id} href={`/teams/${t.slug}`} className="card card-hover group flex flex-col items-center gap-3 overflow-hidden p-5 text-center">
          <span
            className="pointer-events-none absolute inset-x-0 top-0 h-20 opacity-40 transition-opacity group-hover:opacity-70"
            style={{ background: `linear-gradient(180deg, ${t.primary_color || "var(--accent)"}, transparent)` }}
          />
          <span className="relative">
            <TeamMark team={t} size="lg" />
          </span>
          <span className="relative w-full truncate font-display text-xl leading-tight uppercase">{t.name}</span>
          {t.tag && <span className="relative -mt-2 text-xs font-semibold tracking-widest text-muted uppercase">{t.tag}</span>}
        </Link>
      ))}
    </div>
  );
}
