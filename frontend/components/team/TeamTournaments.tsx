"use client";

import Link from "next/link";

import TournamentRegister from "@/components/league/TournamentRegister";
import type { TournamentSummary } from "@/lib/tournaments";
import { useApi } from "@/lib/useApi";

/** The Team page's tournament cards: register (paying DC) while registration is coming up or
 * open, or see the team's invite. Hidden when no tournament takes registrations. */
export default function TeamTournaments({ slug }: { slug: string }) {
  const list = useApi<TournamentSummary[]>("/tournaments");
  const open = (list.data ?? []).filter((t) => t.registration === "soon" || t.registration === "open" || (t.registration === "closed" && t.status !== "finished" && t.status !== "cancelled"));
  if (!open.length) return null;
  return (
    <section className="mt-10">
      <h2 className="font-display text-2xl uppercase">Tournaments</h2>
      <p className="mt-1 text-sm text-muted">Top teams are invited. Every other team registers with DC it has earned.</p>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {open.map((t) => (
          <div key={t.slug}>
            <TournamentRegister slug={t.slug} name={t.name} team={slug} />
            <Link href={`/tournaments/${t.slug}`} className="mt-2 inline-block text-sm text-accent underline">
              {t.name}: teams, prizes and table
            </Link>
          </div>
        ))}
      </div>
    </section>
  );
}
