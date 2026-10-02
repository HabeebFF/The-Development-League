"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, ApiError, type Me } from "@/lib/api";
import { isOpenPath } from "@/lib/home";

import { SkeletonRows } from "./league/Loading";

type Status = "loading" | "in" | "out" | "error";
type Auth = { me: Me | null; status: Status; signOut: () => Promise<void> };

const AuthContext = createContext<Auth>({ me: null, status: "loading", signOut: async () => {} });

export function useAuth(): Auth {
  return useContext(AuthContext);
}

/** Knows who is signed in, and checks again after each page change until someone is. */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  // The page the last "not signed in" answer was for: on any other page, check again first,
  // so arriving from the sign-in form never bounces back to it.
  const [checked, setChecked] = useState<string | null>(null);

  useEffect(() => {
    if (status === "in") return;
    let live = true;
    api<Me>("/me")
      .then((m) => {
        if (!live) return;
        setMe(m);
        setStatus("in");
      })
      .catch((e) => {
        if (!live) return;
        setMe(null);
        setStatus(e instanceof ApiError && (e.status === 401 || e.status === 403) ? "out" : "error");
        setChecked(path);
      });
    return () => {
      live = false;
    };
    // Re-check on every page change while signed out (e.g. right after signing in).
  }, [path, status]);

  const signOut = useCallback(async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } finally {
      setMe(null);
      setStatus("out");
      setChecked(null);
      router.replace("/auth/login");
    }
  }, [router]);

  const current: Status = status === "in" || checked === path ? status : "loading";
  return <AuthContext.Provider value={{ me, status: current, signOut }}>{children}</AuthContext.Provider>;
}

/** The whole site is for signed-in members only; sign-in and invite pages stay open. */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const path = usePathname();
  const router = useRouter();
  const open = isOpenPath(path);

  useEffect(() => {
    if (!open && status === "out") router.replace(`/auth/login?next=${encodeURIComponent(path)}`);
  }, [open, status, path, router]);

  if (open || status === "in") return <>{children}</>;
  if (status === "error")
    return <p className="mx-auto max-w-6xl px-4 py-10 text-bad">Couldn&apos;t reach the server. Try again.</p>;
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <SkeletonRows count={6} />
    </div>
  );
}
