"use client";

import Link from "next/link";

import EmptyState from "@/components/ui/EmptyState";
import { dateSpan, type TournamentSummary } from "@/lib/tournaments";
import { useApi } from "@/lib/useApi";

import Loading from "./Loading";

/** Every tournament, newest first. */
export default function TournamentList() {
  const list = useApi<TournamentSummary[]>("/tournaments");
  if (!list.data) return <Loading error={list.error} />;
  if (!list.data.length) return <EmptyState title="No tournaments yet">Cups and finals show here.</EmptyState>;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {list.data.map((t) => (
        <Link key={t.slug} href={`/tournaments/${t.slug}`} className="card card-hover block p-5">
          <p className="eyebrow">{dateSpan(t.starts_on, t.ends_on) || "Tournament"}</p>
          <p className="mt-1 font-display text-3xl font-black uppercase">{t.name}</p>
          <span className={`mt-2 ${t.status === "live" ? "chip chip-hot" : t.status === "upcoming" ? "chip chip-gold" : "chip"}`}>
            {t.status === "live" ? "● Live" : t.status === "upcoming" ? "Coming up" : "Finished"}
          </span>
        </Link>
      ))}
    </div>
  );
}
