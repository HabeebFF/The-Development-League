"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import Loading from "@/components/league/Loading";
import { api, ApiError, type Paged } from "@/lib/api";
import { bySession, isTwoWay, KINDS, kindOf, type Market } from "@/lib/predictions";
import { useApi } from "@/lib/useApi";

import MarketCard, { MarketRow } from "./MarketCard";
import PredictNav, { NOTE, NotOpen } from "./PredictNav";
import { useWallet } from "./useWallet";

/** Popular picks, then one match at a time (tabs for the session and match, chips for the kind
 * of market), then the latest results. */
export default function PredictHome() {
  const { state } = useWallet();
  const open = useAllOpen();
  const settled = useApi<Paged<Market>>("/predictions/markets?status=settled&page_size=4");
  const popular = useApi<Paged<Market>>("/predictions/markets?status=open&sort=popular&page_size=3");
  const now = useNow();

  if (open.error === "Not found.") return <NotOpen />;
  return (
    <>
      <PredictNav wallet={state} />
      {popular.data && popular.data.results.length > 0 && (
        <section className="mt-8">
          <h2 className="section-title">Popular now</h2>
          <div className="-mx-4 mt-3 flex snap-x gap-3 overflow-x-auto px-4 pb-1 md:mx-0 md:grid md:grid-cols-3 md:overflow-visible md:px-0">
            {popular.data.results.map((m) => (
              <div key={m.id} className="w-[85%] shrink-0 snap-start md:w-auto">
                <MarketCard market={m} now={now} />
              </div>
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
        ) : open.data.length === 0 ? (
          <p className="mt-3 text-muted">No markets are open right now. New ones go up before each session.</p>
        ) : (
          <Board markets={open.data} now={now} />
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

/** Session tabs, match tabs and kind chips over the markets of the chosen match. */
function Board({ markets, now }: { markets: Market[]; now: number }) {
  const sessions = useMemo(() => bySession(markets), [markets]);
  const [sessionKey, setSessionKey] = useState<string | null>(null);
  const [matchKey, setMatchKey] = useState<string | null>(null);
  const [kind, setKind] = useState("all");
  const session = sessions.find((s) => s.key === sessionKey) ?? sessions[0];
  // Open on the next match to start.
  const match = session.matches.find((m) => m.key === matchKey) ?? session.matches[0];
  const kinds = KINDS.filter((k) => match.markets.some((m) => kindOf(m.category) === k.key));
  const shown = kind === "all" ? match.markets : match.markets.filter((m) => kindOf(m.category) === kind);
  const big = shown.filter((m) => !isTwoWay(m));
  const rows = shown.filter(isTwoWay);

  const pick = (fn: () => void) => () => {
    fn();
    setKind("all");
  };

  return (
    <div className="mt-3">
      {sessions.length > 1 && (
        <Tabs>
          {sessions.map((s) => (
            <Tab
              key={s.key}
              on={s.key === session.key}
              onClick={pick(() => {
                setSessionKey(s.key);
                setMatchKey(null);
              })}
              big
            >
              {s.label}
            </Tab>
          ))}
        </Tabs>
      )}
      <Tabs>
        {session.matches.map((m) => (
          <Tab key={m.key} on={m.key === match.key} onClick={pick(() => setMatchKey(m.key))}>
            {m.label}
            <span className="ml-1.5 text-xs text-muted">{m.markets.length}</span>
          </Tab>
        ))}
      </Tabs>
      {kinds.length > 1 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {[{ key: "all", label: "All" }, ...kinds].map((k) => (
            <button
              key={k.key}
              type="button"
              aria-pressed={kind === k.key}
              onClick={() => setKind(k.key)}
              className={`border px-3 py-1 text-sm font-semibold ${kind === k.key ? "border-accent bg-accent/15 text-white" : "border-line text-muted hover:text-white"}`}
            >
              {k.label}
            </button>
          ))}
        </div>
      )}

      {big.length > 0 && (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {big.map((m) => (
            <MarketCard key={m.id} market={m} now={now} />
          ))}
        </div>
      )}
      {rows.length > 0 && (
        <div className="card mt-4 px-4 py-1">
          {rows.map((m) => (
            <MarketRow key={m.id} market={m} />
          ))}
        </div>
      )}
    </div>
  );
}

function Tabs({ children }: { children: React.ReactNode }) {
  return <div className="-mx-4 mt-3 flex gap-1 overflow-x-auto border-b border-line px-4 md:mx-0 md:px-0">{children}</div>;
}

function Tab({ on, onClick, big, children }: { on: boolean; onClick: () => void; big?: boolean; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={`relative shrink-0 px-3 py-2 font-display uppercase transition-colors ${big ? "text-xl" : "text-lg"} ${on ? "text-white" : "text-muted hover:text-white"}`}
    >
      {children}
      {on && <span className="absolute inset-x-2 bottom-0 h-0.5 bg-accent shadow-[0_0_10px_rgb(255_90_31)]" />}
    </button>
  );
}

/** Every open market, page by page, so none is left off the board. */
function useAllOpen(): { data: Market[] | null; error: string | null } {
  const [state, setState] = useState<{ data: Market[] | null; error: string | null }>({ data: null, error: null });
  useEffect(() => {
    let live = true;
    (async () => {
      const all: Market[] = [];
      for (let page = 1; page <= 20; page++) {
        const res = await api<Paged<Market>>(`/predictions/markets?status=open&page_size=100&page=${page}`);
        all.push(...res.results);
        if (!res.next) break;
      }
      if (live) setState({ data: all, error: null });
    })().catch((e) => {
      if (!live) return;
      const error = e instanceof ApiError && e.status === 404 ? "Not found." : e instanceof Error ? e.message : "Couldn't load this.";
      setState({ data: null, error });
    });
    return () => {
      live = false;
    };
  }, []);
  return state;
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
