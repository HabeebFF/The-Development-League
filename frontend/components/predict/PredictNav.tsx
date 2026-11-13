"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { coins } from "@/lib/predictions";

import { useOddsFormat } from "./oddsFormat";
import type { WalletState } from "./useWallet";

const LINKS = [
  { href: "/predict", label: "Markets" },
  { href: "/predict/mine", label: "My predictions" },
  { href: "/predict/wallet", label: "DC" },
  { href: "/predict/leaderboard", label: "Leaderboard" },
  { href: "/predict/shop", label: "Card shop" },
];

/** Tabs across the prediction pages, with the balance (or a sign-up prompt) on the right. */
export default function PredictNav({ wallet }: { wallet: WalletState }) {
  const path = usePathname();
  return (
    <div className="flex flex-col gap-2 md:flex-row md:items-center">
      <nav className="-mx-4 flex gap-1 overflow-x-auto px-4 md:mx-0 md:px-0" aria-label="Predictions">
        {LINKS.map((l) => {
          const on = l.href === "/predict" ? path === "/predict" || path.startsWith("/predict/markets") : path.startsWith(l.href);
          return (
            <Link key={l.href} href={l.href} className={`btn shrink-0 px-4 text-xs uppercase ${on ? "btn-primary" : "btn-ghost"}`}>
              {l.label}
            </Link>
          );
        })}
      </nav>
      <span className="flex items-center justify-between gap-3 md:ml-auto md:justify-end">
        <OddsSwitch />
        <Balance wallet={wallet} />
      </span>
    </div>
  );
}

/** Decimal (2.50) or fractional (6/4) odds: how this viewer likes to read them. */
function OddsSwitch() {
  const [format, setFormat] = useOddsFormat();
  return (
    <span className="flex text-xs" role="group" aria-label="Odds format">
      {(
        [
          ["decimal", "2.50"],
          ["fractional", "6/4"],
        ] as const
      ).map(([key, label]) => (
        <button
          key={key}
          type="button"
          aria-pressed={format === key}
          title={key === "decimal" ? "Decimal odds" : "Fractional odds"}
          className={`btn min-w-11 px-2 ${format === key ? "btn-primary" : "btn-ghost"}`}
          onClick={() => setFormat(key)}
        >
          {label}
        </button>
      ))}
    </span>
  );
}

export function Balance({ wallet }: { wallet: WalletState }) {
  if (wallet.kind === "ok")
    return (
      <span className="flex items-center gap-2">
        {wallet.wallet.bonus ? (
          <span className="chip text-ok" title="Daily bonus: DC for your first visit each day">
            +{wallet.wallet.bonus} today
          </span>
        ) : null}
        <span className="num border border-lion/50 bg-lion/10 px-3 py-1 text-2xl text-accent-hot shadow-[0_0_14px_rgb(245_165_36/0.25)]" aria-label="Your Development Coins (DC)">
          {coins(wallet.wallet.balance)}
        </span>
      </span>
    );
  if (wallet.kind === "out")
    return (
      <span className="flex gap-2">
        <Link href="/auth/signup" className="btn btn-primary px-4 py-1.5 text-sm">
          Sign up to play
        </Link>
        <Link href="/auth/login?next=/predict" className="btn px-4 py-1.5 text-sm">
          Sign in
        </Link>
      </span>
    );
  if (wallet.kind === "staff") return <span className="text-sm text-muted">League staff can&apos;t play.</span>;
  return null;
}

/** Shown in place of a page when predictions are off. */
export function NotOpen() {
  return <p className="text-muted">Predictions aren&apos;t open yet. Check back soon.</p>;
}

export const NOTE = "DC (Development Coin) are play coins: they can't be bought, cashed out or sent to anyone, and have no money value.";
