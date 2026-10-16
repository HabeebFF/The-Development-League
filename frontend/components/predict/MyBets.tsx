"use client";

import Link from "next/link";
import { useState } from "react";

import Loading from "@/components/league/Loading";
import type { Paged } from "@/lib/api";
import { BET_STATUS, coins, MARKET_STATUS, type Bet, type BetStatus, type Multiple } from "@/lib/predictions";
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
  const [kind, setKind] = useState<"bets" | "multiples">("bets");
  const [page, setPage] = useState(1);
  const path = state.kind === "ok" ? `/predictions/${kind}?page=${page}${filter ? `&status=${filter.toLowerCase()}` : ""}` : null;
  const bets = useApi<Paged<Bet | Multiple>>(path);

  if (state.kind === "off") return <NotOpen />;
  return (
    <>
      <PredictNav wallet={state} />
      {state.kind === "ok" && (
        <div className="mt-6 flex flex-wrap gap-1" role="tablist" aria-label="Kind of prediction">
          {(
            [
              ["bets", "Singles"],
              ["multiples", "Multiples"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={kind === key}
              className={`btn px-3 py-1 text-xs uppercase ${kind === key ? "border-accent text-white" : "text-muted"}`}
              onClick={() => {
                setKind(key);
                setPage(1);
              }}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      {state.kind === "ok" && (
        <div className="mt-2 flex flex-wrap gap-1" role="tablist" aria-label="Result">
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
            {kind === "multiples" && (bets.data.results as Multiple[]).map((m) => <MultipleItem key={m.id} m={m} />)}
            {kind === "bets" &&
              (bets.data.results as Bet[]).map((b) => (
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

/** A multiple: its picks with how each settled, and what it returns or paid. */
function MultipleItem({ m }: { m: Multiple }) {
  return (
    <li className="card p-3 text-sm">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <span className="font-semibold">
          {m.picks.length}-pick multiple @ {m.odds}
        </span>
        <span className="text-xs text-muted">{when(m.placed_at)}</span>
        <span className={`ml-auto font-display text-lg uppercase ${BET_STATUS[m.status].tone}`}>{BET_STATUS[m.status].label}</span>
      </div>
      <ul className="mt-2 space-y-1">
        {m.picks.map((p) => (
          <li key={p.market.id} className="flex items-baseline gap-2">
            <span className={`w-20 shrink-0 text-xs uppercase ${BET_STATUS[p.status].tone}`}>{BET_STATUS[p.status].label}</span>
            <span className="min-w-0 flex-1">
              <b>{p.outcome.label}</b>{" "}
              <Link href={`/predict/markets/${p.market.id}`} className="text-muted hover:text-accent">
                {p.market.title}
              </Link>
              {p.dead_heat > 1 && <span className="text-xs text-muted"> · shared by {p.dead_heat}</span>}
            </span>
            <span className="text-accent">{p.odds_accepted}</span>
          </li>
        ))}
      </ul>
      <div className="mt-2 grid grid-cols-2 gap-x-4 sm:grid-cols-3">
        <span>
          <span className="text-muted">Stake</span> {coins(m.stake)}
        </span>
        <span>
          <span className="text-muted">{m.status === "PENDING" ? "Could return" : "Paid"}</span>{" "}
          {m.status === "PENDING" ? coins(m.potential_return) : coins(m.payout ?? 0)}
          {m.status === "PENDING" && m.capped && <span className="text-xs text-muted"> (capped)</span>}
        </span>
        {m.settled_at && <span className="text-muted">settled {when(m.settled_at)}</span>}
      </div>
    </li>
  );
}
