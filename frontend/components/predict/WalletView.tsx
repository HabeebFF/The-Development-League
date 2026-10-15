"use client";

import { useState } from "react";

import Loading from "@/components/league/Loading";
import type { Paged } from "@/lib/api";
import { coins, signedCoins, type Entry } from "@/lib/predictions";
import { useApi } from "@/lib/useApi";

import PredictNav, { NOTE, NotOpen } from "./PredictNav";
import { useWallet } from "./useWallet";

/** Balance and every coin movement, newest first, with the balance after each one. */
export default function WalletView() {
  const { state } = useWallet();
  const [page, setPage] = useState(1);
  const entries = useApi<Paged<Entry>>(state.kind === "ok" ? `/predictions/wallet/entries?page=${page}` : null);

  if (state.kind === "off") return <NotOpen />;
  return (
    <>
      <PredictNav wallet={state} />
      <p className="mt-4 text-xs text-muted">{NOTE}</p>
      <div className="mt-4">
        {state.kind === "out" ? (
          <p className="text-muted">Sign in to see your coins.</p>
        ) : state.kind === "staff" ? (
          <p className="text-muted">League staff can&apos;t play.</p>
        ) : !entries.data ? (
          <Loading error={entries.error} count={5} />
        ) : (
          <div className="overflow-x-auto">
            <table className="table w-full text-sm">
              <thead>
                <tr>
                  <th className="text-left">When</th>
                  <th className="text-left">What</th>
                  <th className="text-right">Coins</th>
                  <th className="text-right">Balance</th>
                </tr>
              </thead>
              <tbody>
                {entries.data.results.map((e) => (
                  <tr key={e.id}>
                    <td className="whitespace-nowrap text-muted">
                      {new Date(e.created_at).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                    </td>
                    <td>
                      {e.kind_label}
                      {e.reason && <span className="block text-xs text-muted">{e.reason}</span>}
                    </td>
                    <td className={`text-right font-semibold ${e.amount > 0 ? "text-ok" : "text-bad"}`}>{signedCoins(e.amount)}</td>
                    <td className="text-right">{coins(e.balance_after)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(entries.data.previous || entries.data.next) && (
              <div className="mt-4 flex gap-2">
                <button type="button" className="btn" disabled={!entries.data.previous} onClick={() => setPage((p) => p - 1)}>
                  Newer
                </button>
                <button type="button" className="btn" disabled={!entries.data.next} onClick={() => setPage((p) => p + 1)}>
                  Older
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
