"use client";

import Link from "next/link";
import { useRef, useState } from "react";

import Loading from "@/components/league/Loading";
import { TeamMark } from "@/components/league/TeamBadge";
import { api, ApiError } from "@/lib/api";
import {
  closesIn,
  coins,
  MARKET_STATUS,
  MAX_STAKE,
  MIN_STAKE,
  newKey,
  profit,
  stakeProblem,
  totalReturn,
  type Bet,
  type Market,
  type Outcome,
} from "@/lib/predictions";
import { useApi } from "@/lib/useApi";

import PredictNav, { NOTE, NotOpen } from "./PredictNav";
import { useNow } from "./PredictHome";
import { useWallet } from "./useWallet";

const QUICK = [10, 50, 100, 250, 500];
// Markets where tied teams share the win (a dead heat).
const SHARED_WIN = new Set(["SESSION_WINNER", "MOST_BOOYAHS", "OVERALL_WINNER"]);

type Placed = Bet & { balance: number };

/** One market: pick a choice, enter a stake, review, confirm. */
export default function MarketView({ id }: { id: number }) {
  const { state: wallet, setBalance } = useWallet();
  const [reload, setReload] = useState(0);
  const market = useApi<Market>(`/predictions/markets/${id}?r=${reload}`);
  const now = useNow();
  const [picked, setPicked] = useState<number | null>(null);
  const [stake, setStake] = useState("100");
  const [review, setReview] = useState<{ outcome: Outcome; stake: number; key: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [placed, setPlaced] = useState<Placed | null>(null);
  const slip = useRef<HTMLElement>(null);

  if (market.error === "Not found.") return <NotOpen />;
  if (!market.data) return <Loading error={market.error} count={4} />;
  const m = market.data;
  const balance = wallet.kind === "ok" ? wallet.wallet.balance : null;
  const outcome = m.outcomes.find((o) => o.id === picked) ?? null;
  const problem = stakeProblem(stake, balance);
  const canPlay = wallet.kind === "ok" && m.accepting && new Date(m.closes_at).getTime() > now;
  const amount = problem ? 0 : Number(stake);

  async function confirm() {
    if (!review) return;
    setBusy(true);
    setError(null);
    try {
      const bet = await api<Placed>("/predictions/bets", {
        method: "POST",
        body: {
          market: m.id,
          outcome: review.outcome.id,
          stake: review.stake,
          client_key: review.key,
          expected_odds: review.outcome.odds,
        },
      });
      setPlaced(bet);
      setBalance(bet.balance);
      setReview(null);
    } catch (e) {
      const data = e instanceof ApiError ? (e.data as { code?: string; detail?: string } | null) : null;
      if (data?.code === "odds_changed" || data?.code === "closed" || data?.code === "outcome") {
        // Something changed on the market: show it fresh and ask again with a new confirmation.
        setReview(null);
        setReload((r) => r + 1);
      }
      setError(
        data?.detail ??
          (e instanceof ApiError ? e.message : "No connection. Your coins weren't touched if this didn't go through; check My predictions."),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PredictNav wallet={wallet} />
      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_22rem]">
        <section>
          <p className="eyebrow">{m.category_label}</p>
          <h2 className="font-display text-3xl uppercase">{m.title}</h2>
          <p className="mt-1 text-sm text-muted">
            {m.fixture ? `${m.fixture.title} · ` : ""}
            {m.season.name} ·{" "}
            <span className={m.accepting ? "text-ok" : ""}>{m.accepting ? closesIn(m.closes_at, now) : MARKET_STATUS[m.status]}</span>
            {" · closes "}
            {new Date(m.closes_at).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit", day: "numeric", month: "short" })}
          </p>
          {m.description && <p className="mt-3 whitespace-pre-line text-sm">{m.description}</p>}
          {SHARED_WIN.has(m.category) && (
            <p className="mt-2 text-xs text-muted">If teams tie for the win, a winning prediction is paid its return divided by the number of tied teams.</p>
          )}

          <div className="mt-5 grid gap-2 sm:grid-cols-2">
            {m.outcomes.map((o) => {
              const on = o.id === picked;
              return (
                <button
                  key={o.id}
                  type="button"
                  disabled={!o.is_active || !canPlay}
                  onClick={() => {
                    setPicked(o.id);
                    setPlaced(null);
                    setError(null);
                    // On phones the slip sits below the choices: bring it into view.
                    if (window.matchMedia("(max-width: 1023px)").matches)
                      setTimeout(() => slip.current?.scrollIntoView({ behavior: "smooth", block: "center" }), 50);
                  }}
                  className={`card flex items-center gap-3 p-3 text-left transition ${on ? "border-accent ring-1 ring-accent" : "card-hover"} disabled:opacity-60`}
                  aria-pressed={on}
                >
                  {o.team && <TeamMark team={o.team} size="md" />}
                  <span className="min-w-0 flex-1 font-semibold">{o.label}</span>
                  {m.winners.includes(o.id) && <span className="chip text-ok">Won</span>}
                  <span className="font-display text-2xl text-accent">{o.odds}</span>
                </button>
              );
            })}
          </div>
          <p className="mt-6 text-xs text-muted">{NOTE}</p>
        </section>

        <aside ref={slip} className="card h-fit p-4 lg:sticky lg:top-[calc(var(--header-h)+1rem)]">
          <h3 className="section-title">Your prediction</h3>
          {placed ? (
            <div className="mt-3 space-y-2 text-sm">
              <p className="font-display text-2xl text-ok uppercase">Prediction placed</p>
              <p>
                {placed.outcome.label} · {coins(placed.stake)} at {placed.odds_accepted}
              </p>
              <p className="text-muted">Pays {coins(placed.potential_return)} if it wins.</p>
              <Link href="/predict/mine" className="btn mt-2 w-full">
                See my predictions
              </Link>
            </div>
          ) : wallet.kind !== "ok" ? (
            <p className="mt-3 text-sm text-muted">
              {wallet.kind === "staff" ? "League staff can't play." : wallet.kind === "out" ? "Sign up or sign in to play." : "Loading your coins..."}
            </p>
          ) : !m.accepting ? (
            <p className="mt-3 text-sm text-muted">This market isn&apos;t taking predictions now.</p>
          ) : !outcome ? (
            <p className="mt-3 text-sm text-muted">Pick a choice.</p>
          ) : (
            <div className="mt-3 space-y-3 text-sm">
              <p>
                <span className="text-muted">Choice:</span> <b>{outcome.label}</b> at <b className="text-accent">{outcome.odds}</b>
              </p>
              <label className="block">
                <span className="text-muted">
                  Stake ({MIN_STAKE} to {MAX_STAKE} coins)
                </span>
                <input
                  className="input mt-1"
                  inputMode="numeric"
                  value={stake}
                  onChange={(e) => setStake(e.target.value)}
                  aria-invalid={!!problem}
                />
              </label>
              <div className="flex flex-wrap gap-1">
                {QUICK.map((q) => (
                  <button key={q} type="button" className="btn px-2 py-1 text-xs" onClick={() => setStake(String(q))}>
                    {q}
                  </button>
                ))}
              </div>
              {problem ? (
                <p className="text-bad">{problem}</p>
              ) : (
                <dl className="grid grid-cols-2 gap-y-1">
                  <dt className="text-muted">Returns if it wins</dt>
                  <dd className="text-right font-semibold">{coins(totalReturn(amount, outcome.odds))}</dd>
                  <dt className="text-muted">Profit</dt>
                  <dd className="text-right font-semibold text-ok">{coins(profit(amount, outcome.odds))}</dd>
                  <dt className="text-muted">Your coins</dt>
                  <dd className="text-right">{balance !== null ? coins(balance) : "–"}</dd>
                </dl>
              )}
              <button
                type="button"
                className="btn btn-primary w-full"
                disabled={!!problem}
                onClick={() => {
                  setError(null);
                  setReview({ outcome, stake: amount, key: newKey() });
                }}
              >
                Review
              </button>
            </div>
          )}
          {error && <p className="mt-3 text-sm text-bad">{error}</p>}
        </aside>
      </div>

      {review && (
        <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/70 p-4 sm:items-center" role="dialog" aria-modal="true" aria-label="Confirm prediction">
          <div className="card page-enter w-full max-w-sm p-5">
            <h3 className="font-display text-2xl uppercase">Confirm prediction</h3>
            <p className="mt-1 text-sm text-muted">{m.title}</p>
            <dl className="mt-4 grid grid-cols-2 gap-y-1.5 text-sm">
              <dt className="text-muted">Choice</dt>
              <dd className="text-right font-semibold">{review.outcome.label}</dd>
              <dt className="text-muted">Stake</dt>
              <dd className="text-right">{coins(review.stake)}</dd>
              <dt className="text-muted">Odds</dt>
              <dd className="text-right">{review.outcome.odds}</dd>
              <dt className="text-muted">Returns if it wins</dt>
              <dd className="text-right font-semibold">{coins(totalReturn(review.stake, review.outcome.odds))}</dd>
              <dt className="text-muted">Profit</dt>
              <dd className="text-right text-ok">{coins(profit(review.stake, review.outcome.odds))}</dd>
              <dt className="text-muted">Coins after</dt>
              <dd className="text-right">{balance !== null ? coins(balance - review.stake) : "–"}</dd>
            </dl>
            <p className="mt-3 text-xs text-muted">If it loses, the stake is gone. The odds are fixed once you confirm.</p>
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
    </>
  );
}
