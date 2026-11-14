// The home page's Fan zone: what fans (accounts that play predictions and shop for card
// designs with DC, play coins with no money value) are doing. One call: /predictions/fan-zone.

import type { CardDesign } from "./cardDesigns";
import type { FanCardData } from "./shop";

export type RankedFan = FanCardData & { rank: number };

export type BoardRow = { rank: number; name: string; net: number; design: CardDesign | null };

export type Leader = { name: string; design: CardDesign | null; value: number; settled?: number };

export type BigWin = {
  name: string;
  design: CardDesign | null;
  /** "SLF to Booyah" for a single, "4-pick multiple" for a multiple. */
  pick: string;
  /** Fixture or market line under the pick, e.g. "Day 33 10PM · Match 2". */
  context: string;
  stake: number;
  payout: number;
  odds: string;
  settled_at: string;
};

export type CrowdPick = {
  market_id: number;
  market: string;
  outcome: string;
  /** Share of the market's backers (fans with a single bet or a multiple pick on it) on this outcome, 0 to 1. */
  share: number;
  backers: number;
  odds: string;
};

export type RareCard = {
  design: CardDesign;
  /** Owners' names, newest first (a Diamond has at most one). */
  owners: string[];
  left: number | null;
};

export type MyFanZone = RankedFan & {
  /** Waiting to be claimed on the predict pages (the home page gives no coins). */
  bonus_ready: boolean;
  daily_bonus: number;
  open_bets: number;
};

/** Which box goes top left: sign up, staff (can't play), signed in without a wallet yet, or their own card. */
export type Viewer = "visitor" | "staff" | "new" | "fan";

export type FanZone = {
  fans: number;
  /** Monday to Sunday, Lagos time; ``starts`` is the Monday. */
  week: { starts: string; bets: number; staked: number; won: number };
  top: RankedFan[];
  board: BoardRow[];
  leaders: { accuracy: Leader | null; wins: Leader | null; min_settled: number };
  big_wins: BigWin[];
  crowd: CrowdPick[];
  rare: RareCard[];
  viewer: Viewer;
  /** Set only when ``viewer`` is "fan". */
  me: MyFanZone | null;
};

/** "x12.50" → "×12.5": odds as a short multiplier. */
export function multiplier(odds: string): string {
  const n = Number(odds);
  if (!Number.isFinite(n)) return odds;
  return `×${Number(n.toFixed(2))}`;
}

/** Profit of a winning bet: what came back minus what went in. */
export function profit(win: Pick<BigWin, "stake" | "payout">): number {
  return Math.max(0, win.payout - win.stake);
}

/** "1st", "2nd", "3rd", "11th", "22nd". */
export function ordinal(n: number): string {
  const tens = n % 100;
  if (tens >= 11 && tens <= 13) return `${n}th`;
  return `${n}${["th", "st", "nd", "rd"][n % 10] ?? "th"}`;
}

/** The podium in show order: 2nd, 1st, 3rd on wide screens (1st stands tallest in the middle). */
export function podium<T extends { rank: number }>(fans: T[]): T[] {
  const by = (r: number) => fans.find((f) => f.rank === r);
  return [by(2), by(1), by(3)].filter((f): f is T => !!f);
}
