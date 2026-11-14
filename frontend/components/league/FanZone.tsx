"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/Auth";
import FanCard from "@/components/predict/FanCard";
import { Swatch } from "@/components/predict/ShopView";
import SectionHeader from "@/components/ui/SectionHeader";
import { multiplier, ordinal, podium, profit, type BigWin, type FanZone as Zone, type Leader, type MyFanZone, type Viewer } from "@/lib/fanZone";
import { coins, percent } from "@/lib/predictions";
import { useApi } from "@/lib/useApi";

import { Skeleton } from "./Loading";

/** Home page Fan zone: your fan card, the top fans' cards, big wins, the crowd's picks and the rarest cards.
 * Hidden when predictions are off (the API answers 404). */
export default function FanZone() {
  const { status } = useAuth();
  // Wait for sign-in to be known, then ask again when it changes, so "me" matches who is looking.
  const zone = useApi<Zone>(status === "loading" ? null : `/predictions/fan-zone?as=${status}`);
  if (zone.error) return null;
  const z = zone.data;
  return (
    <section aria-labelledby="fan-zone">
      <SectionHeader title="Fan zone" href="/predict/leaderboard" link="Fan leaderboard" />
      <p className="-mt-2 mb-5 text-sm text-muted">
        Fans predict every scrim with DC, play coins with no money value, and dress their fan card from the{" "}
        <Link href="/shop" className="text-accent hover:text-accent-hot">
          card shop
        </Link>
        .
      </p>
      {!z ? (
        <div className="grid gap-3 lg:grid-cols-[2fr_3fr]">
          <Skeleton className="h-72" />
          <Skeleton className="h-72" />
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-3 lg:grid-cols-[2fr_3fr]">
            {z.me ? <MyCard me={z.me} /> : <JoinCard viewer={z.viewer} />}
            <Pulse zone={z} />
          </div>
          {z.top.length > 0 && <TopFans zone={z} />}
          <div className="grid gap-3 lg:grid-cols-2">
            <BigWins wins={z.big_wins} />
            <Rare zone={z} />
          </div>
        </div>
      )}
    </section>
  );
}

/** The signed-in fan's own card, place, bonus and open bets. */
function MyCard({ me }: { me: MyFanZone }) {
  return (
    <div className="card flex min-w-0 items-center gap-4 overflow-hidden sm:gap-5 bg-[radial-gradient(80%_120%_at_0%_50%,rgb(245_165_36/0.16),transparent_70%)] p-5">
      <Link href="/shop" className="shrink-0" aria-label="Change your card design in the shop">
        <FanCard fan={me} size={0.62} />
      </Link>
      <div className="min-w-0 flex-1">
        <span className="eyebrow block">Your fan card</span>
        <span className="num mt-1 block text-5xl leading-none">{ordinal(me.rank)}</span>
        <span className="text-xs tracking-[0.14em] text-muted uppercase">on the fan table</span>
        <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
          <dt className="text-muted">Balance</dt>
          <dd className="text-right font-display text-lg">{coins(me.stats.balance)}</dd>
          <dt className="text-muted">Open bets</dt>
          <dd className="text-right font-display text-lg">{me.open_bets}</dd>
        </dl>
        <div className="mt-3 flex flex-wrap gap-2">
          {me.bonus_ready ? (
            <Link href="/predict" className="btn btn-primary px-3 py-1 text-xs">
              Claim {coins(me.daily_bonus)} bonus
            </Link>
          ) : (
            <Link href="/predict" className="btn btn-primary px-3 py-1 text-xs">
              Predict tonight
            </Link>
          )}
          <Link href="/shop" className="btn px-3 py-1 text-xs">
            Card shop
          </Link>
        </div>
      </div>
    </div>
  );
}

/** Visitors: what a fan gets and the way in. Signed in without a wallet: start predicting. Staff: the same pitch, no buttons. */
function JoinCard({ viewer }: { viewer: Viewer }) {
  return (
    <div className="card flex min-w-0 flex-col justify-center gap-3 bg-[radial-gradient(80%_120%_at_0%_50%,rgb(245_165_36/0.16),transparent_70%)] p-6">
      <span className="eyebrow">{viewer === "staff" ? "For fans" : "Become a fan"}</span>
      <p className="font-display text-3xl leading-none font-black uppercase">Get 1,000 DC free</p>
      <p className="text-sm text-muted">
        Pick Booyahs and top fraggers every scrim, climb the fan table and buy a design for your own fan card. Play coins only, never real money.
      </p>
      {viewer === "visitor" && (
        <div className="flex flex-wrap gap-2">
          <Link href="/auth/signup" className="btn btn-primary px-4">
            Sign up free
          </Link>
          <Link href="/auth/login?next=/" className="btn px-4">
            Sign in
          </Link>
        </div>
      )}
      {viewer === "new" && (
        <div>
          <Link href="/predict" className="btn btn-primary px-4">
            Start predicting
          </Link>
        </div>
      )}
    </div>
  );
}

/** This week in numbers, plus where the crowd's coins are for the next session. */
function Pulse({ zone }: { zone: Zone }) {
  const stats: [string, string][] = [
    ["Fans", zone.fans.toLocaleString("en-GB")],
    ["Bets this week", zone.week.bets.toLocaleString("en-GB")],
    ["DC staked", compact(zone.week.staked)],
  ];
  return (
    <div className="card min-w-0 p-5">
      <dl className="grid grid-cols-3 gap-3">
        {stats.map(([label, value]) => (
          <div key={label} className="border-l-2 border-accent/60 pl-3">
            <dt className="text-[10px] font-bold tracking-[0.2em] text-muted uppercase">{label}</dt>
            <dd className="num text-3xl">{value}</dd>
          </div>
        ))}
      </dl>
      <h3 className="mt-5 mb-2 font-display text-sm font-bold tracking-[0.14em] text-muted uppercase">The crowd is backing</h3>
      {zone.crowd.length === 0 ? (
        <p className="text-sm text-muted">Markets open before each session. The fans&apos; favourite picks show here.</p>
      ) : (
        <ul className="space-y-2">
          {zone.crowd.map((c) => (
            <li key={c.market_id}>
              <Link href={`/predict/markets/${c.market_id}`} className="group block">
                <span className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="min-w-0 truncate">
                    <span className="font-semibold group-hover:text-accent">{c.outcome}</span>
                    <span className="text-muted"> · {c.market}</span>
                  </span>
                  <span className="shrink-0 font-display" title={`${c.backers} fans on this market`}>
                    {Math.round(c.share * 100)}%
                  </span>
                </span>
                <span className="mt-1 block h-1.5 bg-line">
                  <span className="block h-full bg-gradient-to-r from-[var(--gold)] to-[var(--gold-hi)]" style={{ width: `${Math.round(c.share * 100)}%` }} />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Top three fan cards on a podium, the next five as a list, and the sharpest and winningest fans. */
function TopFans({ zone }: { zone: Zone }) {
  const narrow = useNarrow();
  return (
    <div className="grid gap-3 lg:grid-cols-[3fr_2fr]">
      <div className="card min-w-0 overflow-hidden bg-[radial-gradient(60%_70%_at_50%_0%,rgb(255_224_138/0.14),transparent_70%)] px-3 pt-5 pb-4">
        <h3 className="mb-3 text-center font-display text-sm font-bold tracking-[0.14em] text-muted uppercase">Top fans by DC</h3>
        <div className="flex items-end justify-center gap-1.5 sm:gap-5">
          {podium(zone.top).map((f) => (
            <div key={f.rank} className={`flex flex-col items-center ${f.rank === 1 ? "" : "pb-3"}`}>
              <FanCard fan={f} size={f.rank === 1 ? (narrow ? 0.5 : 0.58) : narrow ? 0.38 : 0.46} />
              <span className="num mt-1 text-2xl">{ordinal(f.rank)}</span>
              <span className="text-xs text-muted">{coins(f.stats.net)}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="card min-w-0 p-4">
        <ol className="divide-y divide-line">
          {zone.board.map((r) => (
            <li key={r.rank} className="flex items-center gap-3 py-2 text-sm">
              <span className="rank w-7">{r.rank}</span>
              {r.design ? <Swatch design={r.design} size="sm" /> : <span className="w-3" />}
              <span className="min-w-0 flex-1 truncate font-semibold">{r.name}</span>
              <span className="font-display">{coins(r.net)}</span>
            </li>
          ))}
        </ol>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <LeaderTile title="Sharpest" leader={zone.leaders.accuracy} value={(l) => percent(l.value)} empty={`Needs ${zone.leaders.min_settled} settled bets`} />
          <LeaderTile title="Most wins" leader={zone.leaders.wins} value={(l) => `${l.value} won`} empty="No winners yet" />
        </div>
      </div>
    </div>
  );
}

function LeaderTile({ title, leader, value, empty }: { title: string; leader: Leader | null; value: (l: Leader) => string; empty: string }) {
  return (
    <div className="border border-line p-3">
      <span className="eyebrow block">{title}</span>
      {leader ? (
        <>
          <span className="mt-1 flex items-center gap-2 font-semibold">
            {leader.design && <Swatch design={leader.design} size="sm" />}
            <span className="truncate">{leader.name}</span>
          </span>
          <span className="font-display text-xl">{value(leader)}</span>
        </>
      ) : (
        <span className="mt-1 block text-xs text-muted">{empty}</span>
      )}
    </div>
  );
}

/** The week's biggest winning bets, by profit. */
function BigWins({ wins }: { wins: BigWin[] }) {
  return (
    <div className="card min-w-0 p-4">
      <h3 className="mb-3 font-display text-sm font-bold tracking-[0.14em] text-muted uppercase">Big wins this week</h3>
      {wins.length === 0 ? (
        <p className="text-sm text-muted">The week&apos;s biggest winning picks show here once bets settle.</p>
      ) : (
        <ul className="divide-y divide-line">
          {wins.map((w, i) => (
            <li key={i} className="flex items-center gap-3 py-2.5">
              {w.design ? <Swatch design={w.design} /> : <span className="w-9" />}
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold">{w.name}</span>
                <span className="block truncate text-xs text-muted">
                  {w.pick} · {w.context}
                </span>
              </span>
              <span className="text-right">
                <span className="num block text-2xl leading-none text-accent-2">+{compact(profit(w))}</span>
                <span className="text-xs text-muted">
                  {w.stake} at {multiplier(w.odds)}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** The limited designs (Diamond, Vintage, Champion) and who owns them. */
function Rare({ zone }: { zone: Zone }) {
  if (zone.rare.length === 0) return null;
  return (
    <div className="card min-w-0 p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="font-display text-sm font-bold tracking-[0.14em] text-muted uppercase">Rarest cards</h3>
        <Link href="/shop" className="text-xs font-bold tracking-[0.14em] text-accent uppercase">
          Shop &rsaquo;
        </Link>
      </div>
      <ul className="space-y-3">
        {zone.rare.map((r) => (
          <li key={r.design.id} className="flex items-center gap-3">
            <Swatch design={r.design} />
            <span className="min-w-0 flex-1">
              <span className="block font-semibold">{r.design.name}</span>
              <span className="block truncate text-xs text-muted">
                {r.owners.length ? `Owned by ${r.owners.slice(0, 3).join(", ")}${r.owners.length > 3 ? ` +${r.owners.length - 3}` : ""}` : "Nobody owns one yet"}
              </span>
            </span>
            <span className="chip chip-gold shrink-0">{r.left === 0 ? "Sold out" : r.left == null ? "On sale" : `${r.left} left`}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** True on phone widths, where the podium's cards shrink to fit side by side. */
function useNarrow(): boolean {
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const q = window.matchMedia("(max-width: 480px)");
    const update = () => setNarrow(q.matches);
    update();
    q.addEventListener("change", update);
    return () => q.removeEventListener("change", update);
  }, []);
  return narrow;
}

function compact(n: number): string {
  return n >= 10000 ? `${Math.round(n / 1000)}K` : n.toLocaleString("en-GB");
}
