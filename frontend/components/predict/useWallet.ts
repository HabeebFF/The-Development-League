"use client";

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/Auth";
import { api, ApiError } from "@/lib/api";
import type { Wallet } from "@/lib/predictions";

/** "out": not signed in · "staff": staff can't play · "off": predictions are switched off. */
export type WalletState =
  | { kind: "loading" }
  | { kind: "out" }
  | { kind: "staff" }
  | { kind: "off" }
  | { kind: "error"; message: string }
  | { kind: "ok"; wallet: Wallet };

/** The signed-in player's coins, straight from the server (opening it the first time). */
export function useWallet(): { state: WalletState; reload: () => void; setBalance: (n: number) => void } {
  const { status } = useAuth();
  const [fetched, setState] = useState<WalletState>({ kind: "loading" });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (status !== "in") return;
    let live = true;
    api<Wallet>("/predictions/wallet")
      .then((wallet) => live && setState({ kind: "ok", wallet }))
      .catch((e) => {
        if (!live) return;
        if (e instanceof ApiError && e.status === 403) setState({ kind: "staff" });
        else if (e instanceof ApiError && e.status === 404) setState({ kind: "off" });
        else if (e instanceof ApiError && e.status === 401) setState({ kind: "out" });
        else setState({ kind: "error", message: e instanceof Error ? e.message : "Couldn't load your coins." });
      });
    return () => {
      live = false;
    };
  }, [status, tick]);

  const state: WalletState = status === "loading" ? { kind: "loading" } : status !== "in" ? { kind: "out" } : fetched;
  const reload = useCallback(() => setTick((t) => t + 1), []);
  const setBalance = useCallback(
    (balance: number) => setState((s) => (s.kind === "ok" ? { kind: "ok", wallet: { ...s.wallet, balance } } : s)),
    [],
  );
  return { state, reload, setBalance };
}
