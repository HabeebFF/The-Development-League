"use client";

import Link from "next/link";

import { periodLabel, type Trophy } from "@/lib/awards";
import { useApi } from "@/lib/useApi";

/** The team awards a team has won (Team of the week/month, Top kill team, Best IGL). */
export default function TeamTrophies({ slug }: { slug: string }) {
  const data = useApi<{ awards: Trophy[] }>(`/team-awards/${encodeURIComponent(slug)}`);
  const won = data.data?.awards ?? [];
  if (!won.length) return null;
  return (
    <section>
      <h2 className="section-title">Awards won</h2>
      <ul className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {won.map((w) => (
          <li key={`${w.kind}-${w.start}-${w.key}`}>
            <Link
              href={`/awards?period=${w.kind}&date=${w.start}`}
              className="card card-hover block overflow-hidden px-4 py-3"
            >
              <span className="block text-[10px] font-bold tracking-widest text-accent uppercase">
                {w.title} · {periodLabel({ period: w.kind, start: w.start, end: w.end })}
              </span>
              <span className="mt-1 block truncate font-display text-xl uppercase">{w.player ?? w.detail.split(" · ")[0]}</span>
              <span className="block truncate text-xs text-muted">{w.detail}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
