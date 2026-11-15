"use client";

import Link from "next/link";

import { dateSpan, type TournamentSummary } from "@/lib/tournaments";
import { useApi } from "@/lib/useApi";

/** On the home page while a tournament is coming up or live: one line linking to it. */
export default function TournamentBanner() {
  const list = useApi<TournamentSummary[]>("/tournaments");
  const t = list.data?.find((x) => x.status === "live") ?? list.data?.find((x) => x.status === "upcoming");
  if (!t) return null;
  return (
    <Link
      href={`/tournaments/${t.slug}`}
      className="card card-hover mt-6 flex max-w-xl flex-wrap items-center gap-x-3 gap-y-1 border-accent/50 px-4 py-3"
    >
      <span className={t.status === "live" ? "chip chip-hot" : "chip chip-gold"}>{t.status === "live" ? "● Live" : "Coming up"}</span>
      <span className="font-display text-xl font-extrabold uppercase">{t.name}</span>
      <span className="text-sm text-muted">{dateSpan(t.starts_on, t.ends_on)}</span>
      <span className="ml-auto font-display text-sm font-bold tracking-[0.14em] text-accent uppercase">
        Prizes and table <span aria-hidden>&rsaquo;</span>
      </span>
    </Link>
  );
}
