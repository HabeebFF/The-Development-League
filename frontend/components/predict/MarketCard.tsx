"use client";

import Link from "next/link";
import { useState } from "react";

import { TeamMark } from "@/components/league/TeamBadge";
import { closesIn, MARKET_STATUS, ONE_WINNER, showOdds, toPick, type Market, type Outcome } from "@/lib/predictions";

import { useOddsFormat } from "./oddsFormat";
import { useSlip } from "./slip";

const FOLDED = 4;

/** One market in a list: its choices with odds (tap one to add it to the bet slip), and when
 * it closes. Open markets list the likeliest choices first and fold the rest. */
export default function MarketCard({ market, now, fold = true }: { market: Market; now: number; fold?: boolean }) {
  const [all, setAll] = useState(false);
  const open = market.accepting;
  // Shortest odds first while it's open; settled markets keep their order so the winner reads in place.
  const choices = open ? [...market.outcomes].sort((a, b) => Number(a.odds) - Number(b.odds)) : market.outcomes;
  const folded = fold && !all && choices.length > FOLDED + 1;
  const shown = folded ? choices.slice(0, FOLDED) : choices;
  return (
    <div className="card p-4">
      <Link href={`/predict/markets/${market.id}`} className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="eyebrow">{market.category_label}</p>
          <p className="mt-0.5 font-display text-xl leading-tight uppercase hover:text-accent">{market.title}</p>
        </div>
        <span className={`chip shrink-0 ${open ? "text-ok" : "text-muted"}`}>{open ? closesIn(market.closes_at, now) : MARKET_STATUS[market.status]}</span>
      </Link>
      <div className="mt-3 grid gap-1.5 sm:grid-cols-2">
        {shown.map((o) => (
          <Choice key={o.id} market={market} outcome={o} />
        ))}
      </div>
      {folded && (
        <button type="button" onClick={() => setAll(true)} className="mt-2 text-sm font-semibold text-accent hover:underline">
          Show all {choices.length}
        </button>
      )}
      {open && ONE_WINNER.has(market.category) && market.category !== "BOOYAH" && (
        <p className="mt-2 text-xs text-muted">If someone not listed wins it, every pick on this market loses.</p>
      )}
      {market.blocked && open && <p className="mt-2 text-xs text-muted">{market.blocked}</p>}
      {market.predictions > 0 && (
        <p className="mt-2 text-xs text-muted">
          {market.predictions} prediction{market.predictions === 1 ? "" : "s"}
        </p>
      )}
    </div>
  );
}

/** A choice button: team mark, the full name (wrapping, never cut), and the odds. */
function Choice({ market, outcome: o }: { market: Market; outcome: Outcome }) {
  const slip = useSlip();
  const [format] = useOddsFormat();
  const on = slip.has(o.id);
  const won = market.winners.includes(o.id);
  const can = market.accepting && o.is_active && !market.blocked;
  return (
    <button
      type="button"
      disabled={!can}
      aria-pressed={on}
      onClick={() => slip.toggle(toPick(market, o))}
      className={`flex min-h-11 items-center gap-2 border px-2.5 py-1.5 text-left text-sm ${
        on ? "border-accent bg-accent/15" : won ? "border-ok bg-panel-2" : "border-line bg-panel-2"
      } ${o.is_active ? "" : "opacity-40"} ${can ? "hover:border-accent" : "cursor-default"}`}
    >
      {o.team && <TeamMark team={o.team} />}
      <span className="min-w-0 flex-1 leading-tight">{o.label}</span>
      {won && <span className="chip text-ok">Won</span>}
      <span className="font-display text-lg text-accent">{showOdds(o.odds, format)}</span>
    </button>
  );
}

/** A two-choice market on one line: what it's about, then both choices with their odds. */
export function MarketRow({ market }: { market: Market }) {
  const [a, b] = market.outcomes;
  return (
    <div className="flex flex-col gap-2 border-b border-line/60 py-3 last:border-0 sm:flex-row sm:items-center">
      <Link href={`/predict/markets/${market.id}`} className="min-w-0 flex-1 hover:text-accent">
        <span className="block text-[11px] font-bold tracking-widest text-muted uppercase">{market.category_label}</span>
        <span className="block font-semibold leading-tight">{market.title}</span>
      </Link>
      <div className="grid grid-cols-2 gap-1.5 sm:w-[22rem] sm:shrink-0">
        <RowChoice market={market} outcome={a} />
        <RowChoice market={market} outcome={b} />
      </div>
      {market.blocked && market.accepting && <p className="text-xs text-muted sm:hidden">{market.blocked}</p>}
    </div>
  );
}

/** A short label for a two-way choice: "Yes", "Over 19.5", "Berserk -2.5", else the label. */
function short(label: string): string {
  const m = label.match(/^(Yes|No)\b/);
  if (m) return m[1];
  const over = label.match(/(Over|Under) [\d.]+/);
  if (over) return over[0];
  return label.replace(/: (\d+) or more kills$/, ": $1+").replace(/: (\d+) or fewer kills$/, ": $1 or less");
}

function RowChoice({ market, outcome: o }: { market: Market; outcome: Outcome }) {
  const slip = useSlip();
  const [format] = useOddsFormat();
  const on = slip.has(o.id);
  const won = market.winners.includes(o.id);
  const can = market.accepting && o.is_active && !market.blocked;
  return (
    <button
      type="button"
      disabled={!can}
      aria-pressed={on}
      aria-label={`${o.label}, odds ${showOdds(o.odds, format)}`}
      onClick={() => slip.toggle(toPick(market, o))}
      className={`flex min-h-11 items-center gap-2 border px-2.5 py-1.5 text-left text-sm ${
        on ? "border-accent bg-accent/15" : won ? "border-ok bg-panel-2" : "border-line bg-panel-2"
      } ${o.is_active ? "" : "opacity-40"} ${can ? "hover:border-accent" : "cursor-default"}`}
    >
      {o.team && <TeamMark team={o.team} />}
      <span className="min-w-0 flex-1 truncate">{short(o.label)}</span>
      <span className="font-display text-lg text-accent">{showOdds(o.odds, format)}</span>
    </button>
  );
}
