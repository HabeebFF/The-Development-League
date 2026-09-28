"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect } from "react";

import type { Me } from "@/lib/api";
import { useMe } from "@/lib/useMe";

const MeContext = createContext<Me | null>(null);

export function useStaff(): Me {
  const me = useContext(MeContext);
  if (!me) throw new Error("useStaff() outside the staff area");
  return me;
}

export default function StaffGate({ children }: { children: React.ReactNode }) {
  const { me, loading, signedOut } = useMe();
  const router = useRouter();
  const path = usePathname();

  useEffect(() => {
    if (signedOut) router.replace(`/auth/login?next=${encodeURIComponent(path)}`);
  }, [signedOut, router, path]);

  if (loading || signedOut) return <p className="p-6 text-muted">Loading...</p>;
  if (!me) return <p className="p-6 text-bad">Couldn&apos;t reach the server. Try again.</p>;
  if (!me.staff_role) {
    return (
      <div className="mx-auto max-w-xl p-6">
        <p>This area is for league staff.</p>
        <Link href="/" className="mt-4 inline-block text-accent">
          Back home
        </Link>
      </div>
    );
  }
  return <MeContext.Provider value={me}>{children}</MeContext.Provider>;
}
