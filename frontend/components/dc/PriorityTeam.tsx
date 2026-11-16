"use client";

import Link from "next/link";

import { dc } from "@/lib/dc";
import { useDcBoard } from "@/lib/dcBoard";

/** Under the scrim lobby: the team that earned the most DC from matches last week moves up the
 * waitlist first this week. */
export default function PriorityTeam() {
  const board = useDcBoard();
  const p = board?.priority;
  if (!p) return null;
  return (
    <p className="mt-3 text-sm text-muted">
      <span className="font-semibold text-[var(--gold)]">
        DC priority this week:
      </span>{" "}
      <Link href={`/teams/${p.slug}`} className="text-white hover:text-accent">
        {p.name}
      </Link>{" "}
      earned the most DC from matches last week ({dc(p.dc)}), so they move up
      first if a waitlist moves. Nobody loses a place they already have.
    </p>
  );
}
