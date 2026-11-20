"use client";

import Link from "next/link";

import type { Me } from "@/lib/api";

/** Shown instead of a live replay or rotations to accounts that can't watch: they're for the
 * league teams that played the match (staff, managers, and team players whose account is
 * linked to their game UID). ``notTheirMatch``: they're on a team, but it didn't play this one. */
export default function ReplayLock({ me, backHref, notTheirMatch = false }: { me: Me | null; backHref: string; notTheirMatch?: boolean }) {
  const team = me?.memberships.find((m) => m.is_active)?.team;
  let title = "Replays and rotations are for league teams";
  let body = "Players and managers on a league team can watch the matches their team played. Results, standings, kills and cards stay open to everyone.";
  let action: { href: string; label: string } | null = null;
  if (notTheirMatch && me?.can_watch_replays) {
    title = "Only the teams that played";
    body = "Replays and rotations are for the teams that played this match. Ask the league staff if your team should be able to watch every match.";
  } else if (me && team && !me.player) {
    title = "Almost there";
    body = `Replays and rotations are for league teams. You're on ${team.name}: link your Free Fire UID to your account to watch.`;
    action = { href: "/account", label: "Link my UID" };
  } else if (me?.player && !team && !me.staff_role) {
    title = "Join your team to watch";
    body = `You're linked to ${me.player.display_name}. Replays and rotations open once your team's manager accepts you.`;
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
