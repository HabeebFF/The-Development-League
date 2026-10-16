"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import Loading from "@/components/league/Loading";
import type { Paged } from "@/lib/api";
import { byFixture, type Market } from "@/lib/predictions";
import { useApi } from "@/lib/useApi";

import MarketCard from "./MarketCard";
import PredictNav, { NOTE, NotOpen } from "./PredictNav";
import { useWallet } from "./useWallet";

/** The most-predicted open markets, then every open market by match, then the latest results. */
export default function PredictHome() {
  const { state } = useWallet();
  const open = useApi<Paged<Market>>("/predictions/markets?status=open&page_size=100");
  const settled = useApi<Paged<Market>>("/predictions/markets?status=settled&page_size=6");
  const popular = useApi<Paged<Market>>("/predictions/markets?status=open&sort=popular&page_size=4");
  const now = useNow();

  if (open.error === "Not found.") return <NotOpen />;
  return (
    <>
      <PredictNav wallet={state} />
      {popular.data && popular.data.results.length > 0 && (
        <section className="mt-8">
          <h2 className="section-title">Popular now</h2>
          <p className="mt-1 text-sm text-muted">The open markets with the most predictions.</p>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {popular.data.results.map((m) => (
              <MarketCard key={m.id} market={m} now={now} />
            ))}
          </div>
        </section>
      )}

      <section className="mt-8">
        <h2 className="section-title">Open markets</h2>
        {!open.data ? (
          <div className="mt-3">
            <Loading error={open.error} count={4} />
          </div>
        ) : open.data.results.length === 0 ? (
          <p className="mt-3 text-muted">No markets are open right now. New ones go up before each session.</p>
        ) : (
          byFixture(open.data.results).map((group) => (
            <div key={group.key} className="mt-5">
              <h3 className="font-display text-lg text-muted uppercase">{group.title}</h3>
              <div className="mt-2 grid gap-3 md:grid-cols-2">
                {group.markets.map((m) => (
                  <MarketCard key={m.id} market={m} now={now} />
                ))}
              </div>
            </div>
          ))
        )}
      </section>

      {settled.data && settled.data.results.length > 0 && (
        <section className="mt-10">
          <h2 className="section-title">Recent results</h2>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {settled.data.results.map((m) => (
              <MarketCard key={m.id} market={m} now={now} />
            ))}
          </div>
        </section>
      )}

      <p className="mt-10 text-xs text-muted">
        {NOTE}{" "}
        <Link href="/predict/leaderboard" className="text-accent hover:underline">
          See the leaderboard
        </Link>
      </p>
    </>
  );
}

/** The time now, updated every second so countdowns move. */
export function useNow(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  return now;
}
