"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { coins } from "@/lib/predictions";

import type { WalletState } from "./useWallet";

const LINKS = [
  { href: "/predict", label: "Markets" },
  { href: "/predict/mine", label: "My predictions" },
  { href: "/predict/wallet", label: "Coins" },
  { href: "/predict/leaderboard", label: "Leaderboard" },
];

/** Tabs across the prediction pages, with the balance (or a sign-up prompt) on the right. */
export default function PredictNav({ wallet }: { wallet: WalletState }) {
  const path = usePathname();
  return (
    <div className="flex flex-wrap items-center gap-2">
      <nav className="flex flex-wrap gap-1" aria-label="Predictions">
        {LINKS.map((l) => {
          const on = l.href === "/predict" ? path === "/predict" || path.startsWith("/predict/markets") : path.startsWith(l.href);
          return (
            <Link key={l.href} href={l.href} className={`btn px-3 py-1.5 text-xs uppercase ${on ? "border-accent text-white" : "text-muted"}`}>
              {l.label}
            </Link>
          );
        })}
      </nav>
      <span className="ml-auto">
        <Balance wallet={wallet} />
      </span>
    </div>
  );
}

export function Balance({ wallet }: { wallet: WalletState }) {
  if (wallet.kind === "ok")
    return (
      <span className="font-display text-2xl text-accent-2" aria-label="Your coins">
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

export const NOTE = "Play coins only: they can't be bought, cashed out or sent to anyone, and have no money value.";
