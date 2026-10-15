import Link from "next/link";

import { TeamMark } from "@/components/league/TeamBadge";
import { closesIn, MARKET_STATUS, type Market } from "@/lib/predictions";

/** One market in a list: its choices with odds, and when it closes. */
export default function MarketCard({ market, now }: { market: Market; now: number }) {
  return (
    <Link href={`/predict/markets/${market.id}`} className="card card-hover block p-4">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="eyebrow">{market.category_label}</p>
          <p className="mt-0.5 font-display text-xl leading-tight uppercase">{market.title}</p>
        </div>
        <span className={`chip ${market.accepting ? "text-ok" : "text-muted"}`}>
          {market.accepting ? closesIn(market.closes_at, now) : MARKET_STATUS[market.status]}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-1.5 sm:grid-cols-3">
        {market.outcomes.slice(0, 6).map((o) => (
          <span
            key={o.id}
            className={`flex items-center gap-2 border bg-panel-2 px-2 py-1.5 text-sm ${
              market.winners.includes(o.id) ? "border-ok" : "border-line"
            } ${o.is_active ? "" : "opacity-40"}`}
          >
            {o.team && <TeamMark team={o.team} />}
            <span className="min-w-0 flex-1 truncate">{o.label}</span>
            {market.winners.includes(o.id) && <span className="chip text-ok">Won</span>}
            <span className="font-display text-lg text-accent">{o.odds}</span>
          </span>
        ))}
      </div>
      {market.outcomes.length > 6 && <p className="mt-2 text-xs text-muted">+{market.outcomes.length - 6} more choices</p>}
    </Link>
  );
}
