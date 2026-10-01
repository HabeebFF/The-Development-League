"use client";

import Link from "next/link";

import type { Paged } from "@/lib/api";
import { rows, type Team } from "@/lib/league";
import { useApi } from "@/lib/useApi";

import Loading from "./Loading";
import TeamBadge from "./TeamBadge";

/** Every league team. */
export default function TeamsView() {
  const teams = useApi<Paged<Team>>("/teams?page_size=100");
  if (!teams.data) return <Loading error={teams.error} />;
  const all = rows(teams.data).sort((a, b) => a.name.localeCompare(b.name));
  if (!all.length) return <p className="text-muted">No teams yet.</p>;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {all.map((t) => (
        <Link
          key={t.id}
          href={`/teams/${t.slug}`}
          className="flex flex-col items-center gap-3 rounded-lg border border-line bg-panel p-4 text-center hover:border-muted"
        >
          <TeamBadge team={t} size="lg" />
          <span className="w-full truncate font-medium">{t.name}</span>
          {t.tag && <span className="-mt-2 text-xs text-muted">{t.tag}</span>}
        </Link>
      ))}
    </div>
  );
}
