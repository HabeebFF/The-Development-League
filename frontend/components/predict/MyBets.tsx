"use client";

import Link from "next/link";
import { useState } from "react";

import Loading from "@/components/league/Loading";
import type { Paged } from "@/lib/api";
import { BET_STATUS, coins, MARKET_STATUS, type Bet, type BetStatus } from "@/lib/predictions";
import { useApi } from "@/lib/useApi";

import PredictNav, { NotOpen } from "./PredictNav";
import { useWallet } from "./useWallet";

const FILTERS: { key: BetStatus | null; label: string }[] = [
  { key: null, label: "All" },
  { key: "PENDING", label: "Pending" },
  { key: "WON", label: "Won" },
  { key: "LOST", label: "Lost" },
  { key: "VOID", label: "Refunded" },
];

function when(iso: string) {
  return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** The player's own predictions, newest first, filtered by status. */
export default function MyBets() {
  const { state } = useWallet();
  const [filter, setFilter] = useState<BetStatus | null>(null);
  const [page, setPage] = useState(1);
  const path = state.kind === "ok" ? `/predictions/bets?page=${page}${filter ? `&status=${filter.toLowerCase()}` : ""}` : null;
  const bets = useApi<Paged<Bet>>(path);

  if (state.kind === "off") return <NotOpen />;
  return (
    <>
      <PredictNav wallet={state} />
      {state.kind === "ok" && (
        <div className="mt-6 flex flex-wrap gap-1" role="tablist">
          {FILTERS.map((f) => (
            <button
              key={f.label}
              type="button"
              role="tab"
              aria-selected={filter === f.key}
              className={`btn px-3 py-1 text-xs ${filter === f.key ? "border-accent text-white" : "text-muted"}`}
              onClick={() => {
                setFilter(f.key);
                setPage(1);
              }}
            >
              {f.label}
            </button>
          ))}
        </div>
      )}
      <div className="mt-4">
        {state.kind === "out" ? (
          <p className="text-muted">Sign in to see your predictions.</p>
        ) : state.kind === "staff" ? (
          <p className="text-muted">League staff can&apos;t play.</p>
        ) : !bets.data ? (
          <Loading error={bets.error} count={5} />
        ) : bets.data.results.length === 0 ? (
          <p className="text-muted">
            Nothing here yet.{" "}
            <Link href="/predict" className="text-accent hover:underline">
              Find a market
            </Link>
          </p>
        ) : (
          <ul className="space-y-2">
            {bets.data.results.map((b) => (
              <li key={b.id} className="card p-3 text-sm">
                <div className="flex flex-wrap items-baseline gap-x-3">
                  <Link href={`/predict/markets/${b.market.id}`} className="font-semibold hover:text-accent">
                    {b.market.title}
                  </Link>
                  <span className="text-xs text-muted">
                    {b.market.fixture?.title} · market {MARKET_STATUS[b.market.status].toLowerCase()}
                  </span>
                  <span className={`ml-auto font-display text-lg uppercase ${BET_STATUS[b.status].tone}`}>{BET_STATUS[b.status].label}</span>
                </div>
                <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-0.5 sm:grid-cols-4">
                  <span>
                    <span className="text-muted">Pick</span> {b.outcome.label}
                  </span>
                  <span>
                    <span className="text-muted">Stake</span> {coins(b.stake)} @ {b.odds_accepted}
                  </span>
                  <span>
                    <span className="text-muted">{b.status === "PENDING" ? "Could return" : "Paid"}</span>{" "}
                    {b.status === "PENDING" ? coins(b.potential_return) : coins(b.payout ?? 0)}
                  </span>
                  <span className="text-muted">
                    {when(b.placed_at)}
                    {b.settled_at ? ` · settled ${when(b.settled_at)}` : ""}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
        {bets.data && (bets.data.previous || bets.data.next) && (
          <div className="mt-4 flex gap-2">
            <button type="button" className="btn" disabled={!bets.data.previous} onClick={() => setPage((p) => p - 1)}>
              Newer
            </button>
            <button type="button" className="btn" disabled={!bets.data.next} onClick={() => setPage((p) => p + 1)}>
              Older
            </button>
          </div>
        )}
      </div>
    </>
  );
}
