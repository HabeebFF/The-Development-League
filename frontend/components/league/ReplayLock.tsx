"use client";

import Link from "next/link";

import type { Me } from "@/lib/api";

/** Shown instead of a live replay to accounts that can't watch: replays are for league
 * teams (staff, managers, and team players whose account is linked to their game UID). */
export default function ReplayLock({ me, backHref }: { me: Me | null; backHref: string }) {
  const team = me?.memberships.find((m) => m.is_active)?.team;
  let title = "Replays are for league teams only";
  let body = "Players and managers on a league team can watch every match again. Results, standings, kills and rotations stay open to everyone.";
  let action: { href: string; label: string } | null = null;
  if (me && team && !me.player) {
    title = "Almost there";
    body = `Replays are for league teams. You're on ${team.name}: link your Free Fire UID to your account to watch.`;
    action = { href: "/account", label: "Link my UID" };
  } else if (me?.player && !team && !me.staff_role) {
    title = "Join your team to watch";
    body = `You're linked to ${me.player.display_name}. Replays open once your team's manager accepts you.`;
    action = { href: "/account", label: "Ask to join your team" };
  }
  return (
    <section className="mx-auto max-w-xl px-4 py-12">
      <div className="card border-accent/40 p-6 text-center">
        <p className="text-4xl" aria-hidden>
          🔒
        </p>
        <h1 className="mt-2 font-display text-2xl uppercase">{title}</h1>
        <p className="mt-2 text-sm text-muted">{body}</p>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          {action && (
            <Link href={action.href} className="btn btn-primary px-4 py-1.5 text-xs">
              {action.label}
            </Link>
          )}
          {!me && (
            <Link href="/auth/login" className="btn btn-primary px-4 py-1.5 text-xs">
              Sign in
            </Link>
          )}
          <Link href={backHref} className="btn px-4 py-1.5 text-xs">
            Back to the match
          </Link>
        </div>
      </div>
    </section>
  );
}
