"use client";

import Loading from "@/components/league/Loading";
import { TeamMark } from "@/components/league/TeamBadge";
import { closesIn, MARKET_STATUS, RULES, SHARED_WIN, showOdds, toPick, type Market } from "@/lib/predictions";
import { useApi } from "@/lib/useApi";

import PredictNav, { NOTE, NotOpen } from "./PredictNav";
import { useOddsFormat } from "./oddsFormat";
import { useSlip } from "./slip";
import { useNow } from "./PredictHome";
import { useWallet } from "./useWallet";

/** One market: tap a choice to add it to the bet slip (or swap or remove it there). */
export default function MarketView({ id }: { id: number }) {
  const { state: wallet } = useWallet();
  const market = useApi<Market>(`/predictions/markets/${id}`);
  const now = useNow();
  const slip = useSlip();
  const [format] = useOddsFormat();

  if (market.error === "Not found.") return <NotOpen />;
  if (!market.data) return <Loading error={market.error} count={4} />;
  const m = market.data;
  const canPick = m.accepting && !m.blocked && new Date(m.closes_at).getTime() > now;

  return (
    <>
      <PredictNav wallet={wallet} />
      <div className="mt-6 max-w-3xl">
        <section>
          <p className="eyebrow">{m.category_label}</p>
          <h2 className="font-display text-3xl uppercase">{m.title}</h2>
          <p className="mt-1 text-sm text-muted">
            {m.fixture ? `${m.fixture.title} · ` : ""}
            {m.season.name} · <span className={m.accepting ? "text-ok" : ""}>{m.accepting ? closesIn(m.closes_at, now) : MARKET_STATUS[m.status]}</span>
            {" · closes "}
            {new Date(m.closes_at).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit", day: "numeric", month: "short" })}
          </p>
          {m.description && <p className="mt-3 whitespace-pre-line text-sm">{m.description}</p>}
          {RULES[m.category as keyof typeof RULES] && <p className="mt-2 text-xs text-muted">{RULES[m.category as keyof typeof RULES]}</p>}
          {SHARED_WIN.has(m.category) && (
            <p className="mt-2 text-xs text-muted">If several tie for the win, a winning prediction is paid its return divided by the number tied.</p>
          )}

          {m.blocked && m.accepting && <p className="mt-4 border border-line bg-panel-2 p-3 text-sm">{m.blocked}</p>}
          <div className="mt-5 grid gap-2 sm:grid-cols-2">
            {m.outcomes.map((o) => {
              const on = slip.has(o.id);
              return (
                <button
                  key={o.id}
                  type="button"
                  disabled={!o.is_active || !canPick}
                  onClick={() => {
                    slip.toggle(toPick(m, o));
                    if (!on) slip.setOpen(true);
                  }}
                  className={`card flex items-center gap-3 p-3 text-left transition ${on ? "border-accent ring-1 ring-accent" : "card-hover"} disabled:opacity-60`}
                  aria-pressed={on}
                >
                  {(o.team ?? o.player?.team) && <TeamMark team={(o.team ?? o.player?.team)!} size="md" />}
                  <span className="min-w-0 flex-1">
                    <span className="block font-semibold">{o.label}</span>
                    {o.player?.team && <span className="block text-xs text-muted">{o.player.team.name}</span>}
                  </span>
                  {m.winners.includes(o.id) && <span className="chip text-ok">Won</span>}
                  <span className="font-display text-2xl text-accent">{showOdds(o.odds, format)}</span>
                </button>
              );
            })}
          </div>
          {canPick && <p className="mt-3 text-xs text-muted">Tap a choice to add it to your bet slip. Add picks from other matches to make a multiple.</p>}
          <p className="mt-6 text-xs text-muted">{NOTE}</p>
        </section>
      </div>
    </>
  );
}
