"use client";

import Link from "next/link";

import { useAuth } from "../Auth";

/** For signed-in fans: "Play in the league? Link your UID" (to My account). Nothing for
 * visitors, staff, linked players or a UID already waiting for staff. */
export default function LinkUidPrompt({ what = "your card" }: { what?: string }) {
  const { me, status } = useAuth();
  if (status !== "in" || !me || me.staff_role || me.player || me.pending_uid_claim) return null;
  return (
    <div className="card mb-6 flex flex-wrap items-center gap-3 border-accent/40 p-3 text-sm">
      <p className="min-w-0 flex-1">
        <b>Play in the league?</b> <span className="text-muted">Link your Free Fire UID to see {what}. You keep your DC and designs.</span>
      </p>
      <Link href="/account" className="btn btn-primary px-4 py-1.5 text-xs">
        Link my UID
      </Link>
    </div>
  );
}
