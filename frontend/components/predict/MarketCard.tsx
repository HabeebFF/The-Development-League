"use client";

import Link from "next/link";

import { TeamMark } from "@/components/league/TeamBadge";
import { closesIn, MARKET_STATUS, showOdds, toPick, type Market } from "@/lib/predictions";

import { useOddsFormat } from "./oddsFormat";
import { useSlip } from "./slip";

/** One market in a list: its choices with odds (tap one to add it to the bet slip), and
 * when it closes. */
export default function MarketCard({ market, now }: { market: Market; now: number }) {
  const slip = useSlip();
  const [format] = useOddsFormat();
  return (
    <div className="card card-hover p-4">
      <Link href={`/predict/markets/${market.id}`} className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="eyebrow">{market.category_label}</p>
          <p className="mt-0.5 font-display text-xl leading-tight uppercase hover:text-accent">{market.title}</p>
        </div>
        <span className={`chip ${market.accepting ? "text-ok" : "text-muted"}`}>
          {market.accepting ? closesIn(market.closes_at, now) : MARKET_STATUS[market.status]}
        </span>
      </Link>
      <div className="mt-3 grid grid-cols-2 gap-1.5 sm:grid-cols-3">
        {market.outcomes.slice(0, 6).map((o) => {
          const on = slip.has(o.id);
          const can = market.accepting && o.is_active && !market.blocked;
          return (
            <button
              key={o.id}
              type="button"
              disabled={!can}
              aria-pressed={on}
              onClick={() => slip.toggle(toPick(market, o))}
              className={`flex items-center gap-2 border px-2 py-1.5 text-left text-sm ${
                on ? "border-accent bg-accent/15" : market.winners.includes(o.id) ? "border-ok bg-panel-2" : "border-line bg-panel-2"
              } ${o.is_active ? "" : "opacity-40"} ${can ? "hover:border-accent" : "cursor-default"}`}
            >
              {o.team && <TeamMark team={o.team} />}
              <span className="min-w-0 flex-1 truncate">{o.label}</span>
              {market.winners.includes(o.id) && <span className="chip text-ok">Won</span>}
              <span className="font-display text-lg text-accent">{showOdds(o.odds, format)}</span>
            </button>
          );
        })}
      </div>
      {market.blocked && market.accepting && <p className="mt-2 text-xs text-muted">{market.blocked}</p>}
      {market.predictions > 0 && (
        <p className="mt-2 text-xs text-muted">
          {market.predictions} prediction{market.predictions === 1 ? "" : "s"}
        </p>
      )}
      {market.outcomes.length > 6 && (
        <Link href={`/predict/markets/${market.id}`} className="mt-2 block text-xs text-muted hover:text-accent">
          +{market.outcomes.length - 6} more choices
        </Link>
      )}
    </div>
  );
}
