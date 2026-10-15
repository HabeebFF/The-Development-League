"use client";

import { useState } from "react";

import Loading from "@/components/league/Loading";
import { coins, METRICS, percent, type Leaderboard, type Metric } from "@/lib/predictions";
import { useApi } from "@/lib/useApi";

import PredictNav, { NotOpen } from "./PredictNav";
import { useWallet } from "./useWallet";

/** Three separate tables (coins, accuracy, wins), each with what it measures. */
export default function LeaderboardView() {
  const { state } = useWallet();
  const [metric, setMetric] = useState<Metric>("balance");
  const board = useApi<Leaderboard>(`/predictions/leaderboard?metric=${metric}`);
  const info = METRICS.find((m) => m.key === metric)!;

  if (board.error === "Not found.") return <NotOpen />;
  return (
    <>
      <PredictNav wallet={state} />
      <div className="mt-6 flex flex-wrap gap-1" role="tablist">
        {METRICS.map((m) => (
          <button
            key={m.key}
            type="button"
            role="tab"
            aria-selected={metric === m.key}
            className={`btn px-3 py-1 text-xs uppercase ${metric === m.key ? "border-accent text-white" : "text-muted"}`}
            onClick={() => setMetric(m.key)}
          >
            {m.label}
          </button>
        ))}
      </div>
      <p className="mt-2 text-sm text-muted">{info.explain(board.data?.accuracy_min_settled ?? 10)}</p>
      <div className="mt-4">
        {!board.data ? (
          <Loading error={board.error} count={8} />
        ) : board.data.rows.length === 0 ? (
          <p className="text-muted">Nobody qualifies yet.</p>
        ) : (
          <table className="table w-full text-sm">
            <thead>
              <tr>
                <th className="w-12 text-left">#</th>
                <th className="text-left">Player</th>
                <th className="text-right">{info.label}</th>
                <th className="hidden text-right sm:table-cell">Won / lost</th>
              </tr>
            </thead>
            <tbody>
              {board.data.rows.map((r) => (
                <tr key={r.rank} className={r.is_me ? "bg-accent/10" : ""}>
                  <td>
                    <span className={`rank ${r.rank <= 3 ? `rank-${r.rank}` : ""}`}>{r.rank}</span>
                  </td>
                  <td className="font-semibold">
                    {r.name}
                    {r.is_me && <span className="ml-2 chip text-accent">You</span>}
                  </td>
                  <td className="text-right font-display text-lg">
                    {metric === "balance" ? coins(r.balance) : metric === "accuracy" ? percent(r.accuracy) : r.won}
                  </td>
                  <td className="hidden text-right text-muted sm:table-cell">
                    {r.won} / {r.lost}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
