"use client";

import Link from "next/link";
import { useState } from "react";
import { createPortal } from "react-dom";

import { api, ApiError } from "@/lib/api";
import {
  coins,
  combinedOdds,
  MAX_PICKS,
  MAX_RETURN,
  MAX_STAKE,
  MIN_STAKE,
  multipleReturn,
  newKey,
  slipProblem,
  stakeProblem,
  type Bet,
  type Multiple,
  type SlipPick,
} from "@/lib/predictions";

import { NOTE } from "./PredictNav";
import { useSlip } from "./slip";
import { useWallet } from "./useWallet";

const QUICK = [10, 50, 100, 250, 500];

type Review = { picks: SlipPick[]; stake: number; key: string };
type Placed = { kind: "single"; bet: Bet } | { kind: "multiple"; multiple: Multiple };
type Refusal = { code?: string; detail?: string; market?: number; odds?: string; markets?: number[] };

/** The bet slip: a bar along the bottom of every prediction page that opens into the slip.
 * One pick is placed as a single, two or more as a multiple. */
export default function BetSlip() {
  const slip = useSlip();
  const { state: wallet, setBalance } = useWallet();
  const [stake, setStake] = useState("100");
  const [review, setReview] = useState<Review | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flagged, setFlagged] = useState<number[]>([]);
  const [placed, setPlaced] = useState<Placed | null>(null);

  const { picks } = slip;
  // Nothing on the server render: the picks are only known in the browser.
  if ((picks.length === 0 && !placed) || typeof document === "undefined") return null;

  const balance = wallet.kind === "ok" ? wallet.wallet.balance : null;
  const odds = picks.map((p) => p.odds);
  const multiple = picks.length > 1;
  const shown = multiple ? combinedOdds(odds) : (odds[0] ?? "");
  const stakeNote = stakeProblem(stake, balance);
  const picksNote = slipProblem(picks);
  const amount = stakeNote ? 0 : Number(stake);
  const returns = multipleReturn(amount, odds);

  async function confirm() {
    if (!review) return;
    setBusy(true);
    setError(null);
    try {
      if (review.picks.length === 1) {
        const [p] = review.picks;
        const bet = await api<Bet & { balance: number }>("/predictions/bets", {
          method: "POST",
          body: { market: p.market, outcome: p.outcome, stake: review.stake, client_key: review.key, expected_odds: p.odds },
        });
        setBalance(bet.balance);
        setPlaced({ kind: "single", bet });
      } else {
        const made = await api<Multiple & { balance: number }>("/predictions/multiples", {
          method: "POST",
          body: {
            picks: review.picks.map((p) => ({ market: p.market, outcome: p.outcome, expected_odds: p.odds })),
            stake: review.stake,
            client_key: review.key,
          },
        });
        setBalance(made.balance);
        setPlaced({ kind: "multiple", multiple: made });
      }
      slip.clear();
      setFlagged([]);
      setReview(null);
    } catch (e) {
      const data = e instanceof ApiError ? (e.data as Refusal | null) : null;
      if (data?.code) {
        // Something changed: show it on the slip and ask again with a new confirmation.
        setReview(null);
        // A single's refusal doesn't name the market: it's the only pick.
        const market = data.market ?? (review.picks.length === 1 ? review.picks[0].market : undefined);
        if (data.code === "odds_changed" && data.odds && market !== undefined) slip.setOdds(market, data.odds);
        setFlagged(data.markets ?? (market !== undefined ? [market] : []));
      }
      setError(
        data?.detail ?? (e instanceof ApiError ? e.message : "No connection. Your coins weren't touched if this didn't go through; check My predictions."),
      );
    } finally {
      setBusy(false);
    }
  }

  // Into <body>: page transitions transform the page, which would carry a fixed bar with it.
  return createPortal(
    <>
      {/* Above the phone tab bar (its height is 0 on wider screens). */}
      <div className="fixed inset-x-0 bottom-[calc(var(--bottom-nav-h)+env(safe-area-inset-bottom))] z-30 px-2 pb-2 sm:left-auto sm:right-4 sm:bottom-[calc(var(--bottom-nav-h)+1rem)] sm:w-96 sm:px-0 sm:pb-0">
        <div className="card overflow-hidden shadow-2xl shadow-black/60">
          <button
            type="button"
            className="flex w-full items-center gap-3 bg-panel-2 px-4 py-3 text-left"
            aria-expanded={slip.open}
            onClick={() => slip.setOpen(!slip.open)}
          >
            <span className="font-display text-lg uppercase">Bet slip</span>
            {picks.length > 0 && <span className="chip text-accent-2">{picks.length}</span>}
            <span className="ml-auto text-sm text-muted">{picks.length === 0 ? "Placed" : multiple ? `Multiple @ ${shown}` : `Single @ ${shown}`}</span>
            <span aria-hidden className="text-muted">
              {slip.open ? "▾" : "▴"}
            </span>
          </button>

          {slip.open && (
            <div className="max-h-[70vh] space-y-3 overflow-y-auto p-4 text-sm">
              {placed && picks.length === 0 ? (
                <PlacedNote placed={placed} onDone={() => setPlaced(null)} />
              ) : (
                <>
                  <ul className="space-y-1.5">
                    {picks.map((p) => (
                      <li
                        key={p.market}
                        className={`flex items-start gap-2 border bg-panel-2 px-2 py-1.5 ${flagged.includes(p.market) ? "border-bad" : "border-line"}`}
                      >
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-semibold">{p.label}</span>
                          <Link href={`/predict/markets/${p.market}`} className="block truncate text-xs text-muted hover:text-accent">
                            {p.marketTitle}
                            {p.fixture ? ` · ${p.fixture.title}` : ""}
                          </Link>
                        </span>
                        <span className="font-display text-lg text-accent">{p.odds}</span>
                        <button
                          type="button"
                          className="px-1 text-muted hover:text-bad"
                          aria-label={`Remove ${p.label}`}
                          onClick={() => {
                            slip.remove(p.market);
                            setFlagged(flagged.filter((m) => m !== p.market));
                            setError(null);
                          }}
                        >
                          ×
                        </button>
                      </li>
                    ))}
                  </ul>
                  {multiple && (
                    <p className="text-xs text-muted">
                      Multiple: the odds multiply and every pick has to win. A refunded pick drops out and the rest still count. Up to {MAX_PICKS} picks, never
                      on the same match.
                    </p>
                  )}
                  {picksNote ? (
                    <p className="text-bad">{picksNote}</p>
                  ) : wallet.kind !== "ok" ? (
                    <p className="text-muted">
                      {wallet.kind === "staff" ? (
                        "League staff can't play."
                      ) : (
                        <>
                          <Link href="/auth/signup" className="text-accent hover:underline">
                            Sign up
                          </Link>{" "}
                          or{" "}
                          <Link href="/auth/login?next=/predict" className="text-accent hover:underline">
                            sign in
                          </Link>{" "}
                          to place it.
                        </>
                      )}
                    </p>
                  ) : (
                    <>
                      <label className="block">
                        <span className="text-muted">
                          Stake ({MIN_STAKE} to {MAX_STAKE} coins)
                        </span>
                        <input className="input mt-1" inputMode="numeric" value={stake} onChange={(e) => setStake(e.target.value)} aria-invalid={!!stakeNote} />
                      </label>
                      <div className="flex flex-wrap gap-1">
                        {QUICK.map((q) => (
                          <button key={q} type="button" className="btn px-2 py-1 text-xs" onClick={() => setStake(String(q))}>
                            {q}
                          </button>
                        ))}
                      </div>
                      {stakeNote ? (
                        <p className="text-bad">{stakeNote}</p>
                      ) : (
                        <dl className="grid grid-cols-2 gap-y-1">
                          <dt className="text-muted">Odds</dt>
                          <dd className="text-right">{shown}</dd>
                          <dt className="text-muted">Returns if it wins</dt>
                          <dd className="text-right font-semibold">{coins(returns)}</dd>
                          <dt className="text-muted">Profit</dt>
                          <dd className="text-right font-semibold text-ok">{coins(returns - amount)}</dd>
                          <dt className="text-muted">Your coins</dt>
                          <dd className="text-right">{balance !== null ? coins(balance) : "–"}</dd>
                        </dl>
                      )}
                      {returns >= MAX_RETURN && <p className="text-xs text-muted">Returns are capped at {coins(MAX_RETURN)}.</p>}
                      <button
                        type="button"
                        className="btn btn-primary w-full"
                        disabled={!!stakeNote}
                        onClick={() => {
                          setError(null);
                          setReview({ picks, stake: amount, key: newKey() });
                        }}
                      >
                        Review {multiple ? `${picks.length}-pick multiple` : "prediction"}
                      </button>
                    </>
                  )}
                  {error && <p className="text-bad">{error}</p>}
                  <div className="flex items-center justify-between text-xs">
                    <button type="button" className="text-muted hover:text-bad" onClick={() => slip.clear()}>
                      Clear slip
                    </button>
                    <span className="text-muted">Play coins only</span>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {review && (
        <div
          className="fixed inset-0 z-40 flex items-end justify-center bg-black/70 p-4 sm:items-center"
          role="dialog"
          aria-modal="true"
          aria-label="Confirm prediction"
        >
          <div className="card page-enter max-h-[90vh] w-full max-w-sm overflow-y-auto p-5">
            <h3 className="font-display text-2xl uppercase">
              {review.picks.length > 1 ? `Confirm ${review.picks.length}-pick multiple` : "Confirm prediction"}
            </h3>
            <ul className="mt-3 space-y-1 text-sm">
              {review.picks.map((p) => (
                <li key={p.market} className="flex gap-2">
                  <span className="min-w-0 flex-1">
                    <b>{p.label}</b>
                    <span className="block truncate text-xs text-muted">{p.marketTitle}</span>
                  </span>
                  <span className="text-accent">{p.odds}</span>
                </li>
              ))}
            </ul>
            <dl className="mt-4 grid grid-cols-2 gap-y-1.5 text-sm">
              <dt className="text-muted">Stake</dt>
              <dd className="text-right">{coins(review.stake)}</dd>
              <dt className="text-muted">Odds</dt>
              <dd className="text-right">{combinedOdds(review.picks.map((p) => p.odds))}</dd>
              <dt className="text-muted">Returns if it wins</dt>
              <dd className="text-right font-semibold">
                {coins(
                  multipleReturn(
                    review.stake,
                    review.picks.map((p) => p.odds),
                  ),
                )}
              </dd>
              <dt className="text-muted">Coins after</dt>
              <dd className="text-right">{balance !== null ? coins(balance - review.stake) : "–"}</dd>
            </dl>
            <p className="mt-3 text-xs text-muted">
              {review.picks.length > 1 ? "If any pick loses, the whole stake is gone." : "If it loses, the stake is gone."} The odds are fixed once you confirm.{" "}
              {NOTE}
            </p>
            {error && <p className="mt-2 text-sm text-bad">{error}</p>}
            <div className="mt-4 grid grid-cols-2 gap-2">
              <button type="button" className="btn" onClick={() => setReview(null)} disabled={busy}>
                Back
              </button>
              {/* A retry after a network error reuses the same key, so it can't be a second bet. */}
              <button type="button" className="btn btn-primary" onClick={confirm} disabled={busy}>
                {busy ? "Placing..." : "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>,
    document.body,
  );
}

function PlacedNote({ placed, onDone }: { placed: Placed; onDone: () => void }) {
  return (
    <div className="space-y-2">
      <p className="font-display text-2xl text-ok uppercase">{placed.kind === "multiple" ? "Multiple placed" : "Prediction placed"}</p>
      {placed.kind === "single" ? (
        <p>
          {placed.bet.outcome.label} · {coins(placed.bet.stake)} at {placed.bet.odds_accepted}. Pays {coins(placed.bet.potential_return)} if it wins.
        </p>
      ) : (
        <p>
          {placed.multiple.picks.length} picks · {coins(placed.multiple.stake)} at {placed.multiple.odds}. Pays {coins(placed.multiple.potential_return)} if
          every pick wins.
        </p>
      )}
      <div className="grid grid-cols-2 gap-2">
        <Link href="/predict/mine" className="btn" onClick={onDone}>
          My predictions
        </Link>
        <button type="button" className="btn" onClick={onDone}>
          Done
        </button>
      </div>
    </div>
  );
}
