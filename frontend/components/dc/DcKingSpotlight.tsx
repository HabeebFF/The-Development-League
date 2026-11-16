"use client";

import Link from "next/link";

import { dc, kingMonth } from "@/lib/dc";
import { useDcBoard } from "@/lib/dcBoard";

/** Home page: last month's DC King, all month long. */
export default function DcKingSpotlight() {
  const board = useDcBoard();
  const king = board?.king;
  if (!king) return null;
  const month = kingMonth(king.month);
  return (
    <section>
      <Link href={`/cards/${king.player_id}`} className="card card-hover flex items-center gap-4 overflow-hidden border-l-4 border-[var(--gold)] p-4">
        {king.photo ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={king.photo} alt="" className="h-20 w-20 shrink-0 rounded-full bg-panel-2 object-cover object-top" />
        ) : (
          <span className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full bg-panel-2 font-display text-3xl text-[var(--gold)]">
            {king.name.slice(0, 1)}
          </span>
        )}
        <div className="min-w-0">
          <p className="eyebrow text-[var(--gold)]">DC King · {month}</p>
          <h2 className="truncate font-display text-3xl uppercase">{king.name}</h2>
          <p className="text-sm text-muted">
            {king.team ? `${king.team.name} · ` : ""}
            {dc(king.earned)} earned in {month.charAt(0) + month.slice(1).toLowerCase()}
            {king.from_matches ? `, ${dc(king.from_matches)} of it from matches` : ""}
          </p>
        </div>
      </Link>
    </section>
  );
}
