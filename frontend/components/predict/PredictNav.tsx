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
            <Link key={l.href} href={l.href} className={`btn shrink-0 px-3 py-1.5 text-xs uppercase ${on ? "border-accent text-white" : "text-muted"}`}>
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
          className={`btn px-2 py-1 ${format === key ? "border-accent text-white" : "text-muted"}`}
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
      <span className="border border-accent-2/40 bg-accent-2/10 px-3 py-0.5 font-display text-xl text-accent-2" aria-label="Your Development Coins (DC)">
        {coins(wallet.wallet.balance)}
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
