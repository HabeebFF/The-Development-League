"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect } from "react";

import JoinTeam from "@/components/account/JoinTeam";
import NewTeam from "@/components/account/NewTeam";
import type { Me, Membership } from "@/lib/api";
import { useMe } from "@/lib/useMe";

type TeamContext = { me: Me; membership: Membership | null };

const Context = createContext<TeamContext | null>(null);

/** The signed-in user and their team (null for league staff who aren't on a team). */
export function useTeam(): TeamContext {
  const value = useContext(Context);
  if (!value) throw new Error("useTeam() outside the team area");
  return value;
}

export default function TeamGate({ children }: { children: React.ReactNode }) {
  const { me, loading, signedOut } = useMe();
  const router = useRouter();
  const path = usePathname();

  useEffect(() => {
    if (signedOut) router.replace(`/auth/login?next=${encodeURIComponent(path)}`);
  }, [signedOut, router, path]);

  if (loading || signedOut) return <p className="p-6 text-muted">Loading...</p>;
  if (!me) return <p className="p-6 text-bad">Couldn&apos;t reach the server. Try again.</p>;
  const membership = me.memberships.find((m) => m.is_active) ?? null;
  if (!membership && !me.staff_role) {
    return (
      <div className="mx-auto max-w-xl space-y-4 p-6">
        <p>Your account isn&apos;t on a team yet. Ask to join below, or ask your team manager to send you an invite.</p>
        {me.player ? (
          <JoinTeam />
        ) : (
          <p className="text-sm text-muted">
            First link your Free Fire UID on{" "}
            <Link href="/account" className="text-accent">
              My account
            </Link>
            , so your manager can see who&apos;s asking.
          </p>
        )}
        <div className="card p-4 text-sm">
          <p className="font-display text-lg uppercase">Managing a new team?</p>
          <p className="mt-1 text-muted">Create it with its roster and UIDs. Once TDL staff approve it you can sign up for scrims.</p>
          <Link href="/create-team" className="btn btn-primary mt-3 px-4 py-1.5 text-xs">
            Create your team
          </Link>
        </div>
        <Link href="/" className="mt-4 inline-block text-accent">
          Back home
        </Link>
      </div>
    );
  }
  // A team that created itself waits for staff before the team area opens.
  if (membership && membership.team.status && membership.team.status !== "APPROVED") {
    return (
      <div className="mx-auto max-w-3xl space-y-4 px-4 py-10">
        <p className="text-sm font-semibold tracking-[0.2em] text-accent uppercase">Team manager</p>
        {membership.role === "MANAGER" ? (
          <NewTeam />
        ) : (
          <p className="text-muted">{membership.team.name} is waiting for TDL staff to approve it.</p>
        )}
      </div>
    );
  }
  return <Context.Provider value={{ me, membership }}>{children}</Context.Provider>;
}
