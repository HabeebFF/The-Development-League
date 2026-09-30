"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect } from "react";

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
      <div className="mx-auto max-w-xl p-6">
        <p>Your account isn&apos;t on a team yet. Ask your team manager to send you an invite.</p>
        <Link href="/" className="mt-4 inline-block text-accent">
          Back home
        </Link>
      </div>
    );
  }
  return <Context.Provider value={{ me, membership }}>{children}</Context.Provider>;
}
