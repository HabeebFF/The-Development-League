// Virtual-coin predictions: types from the API and small helpers the pages share.
// The server works out every real number (balance, accepted odds, payouts); the
// sums here only preview what the server will say.

export type PTeam = { id: number; name: string; tag: string; slug: string; logo: string | null; primary_color: string };

export type Fixture = {
  id: number;
  title: string;
  date: string;
  session: string;
  match_number: number | null;
  scheduled_at: string;
  match: number | null;
};

export type MarketStatus = "DRAFT" | "OPEN" | "SUSPENDED" | "CLOSED" | "SETTLED" | "VOID";
export type BetStatus = "PENDING" | "WON" | "LOST" | "VOID";

export type Outcome = { id: number; code: string; label: string; team: PTeam | null; odds: string; is_active: boolean };

export type Market = {
  id: number;
  title: string;
  description: string;
  category: string;
  category_label: string;
  season: { id: number; name: string };
  fixture: Fixture | null;
  status: MarketStatus;
  accepting: boolean;
  opens_at: string;
  closes_at: string;
  /** Winning outcome ids once settled. */
  winners: number[];
  outcomes: Outcome[];
};

export type Bet = {
  id: string;
  market: { id: number; title: string; status: MarketStatus; fixture: Fixture | null };
  outcome: { id: number; label: string };
  stake: number;
  odds_accepted: string;
  potential_return: number;
  potential_profit: number;
  payout: number | null;
  status: BetStatus;
  placed_at: string;
  settled_at: string | null;
};

export type Wallet = { balance: number; starting_coins: number; created_at: string };

export type Entry = {
  id: string;
  seq: number;
  kind: string;
  kind_label: string;
  amount: number;
  balance_before: number;
  balance_after: number;
  reason: string;
  created_at: string;
};

export type Metric = "balance" | "accuracy" | "wins";
export type LeaderRow = {
  rank: number;
  name: string;
  is_me: boolean;
  balance: number;
  won: number;
  lost: number;
  accuracy: number | null;
};
export type Leaderboard = { metric: Metric; accuracy_min_settled: number; rows: LeaderRow[] };

export const MIN_STAKE = 10;
export const MAX_STAKE = 500;

/** Odds "2.55" as whole hundredths (255), so sums stay exact. */
function hundredths(odds: string): number {
  const [whole, frac = ""] = odds.split(".");
  return Number(whole) * 100 + Number((frac + "00").slice(0, 2));
}

/** Stake x odds, rounded down to a whole coin: the same sum the server makes. */
export function totalReturn(stake: number, odds: string): number {
  return Math.floor((stake * hundredths(odds)) / 100);
}

export function profit(stake: number, odds: string): number {
  return totalReturn(stake, odds) - stake;
}

/** Why a stake can't be used, or null when it can. */
export function stakeProblem(text: string, balance: number | null): string | null {
  if (!/^\d+$/.test(text.trim())) return "Enter a whole number of coins.";
  const stake = Number(text);
  if (stake < MIN_STAKE) return `The smallest stake is ${MIN_STAKE} coins.`;
  if (stake > MAX_STAKE) return `The biggest stake is ${MAX_STAKE} coins.`;
  if (balance !== null && stake > balance) return `You only have ${coins(balance)}.`;
  return null;
}

export function coins(n: number): string {
  return `${n.toLocaleString("en-GB")} ${Math.abs(n) === 1 ? "coin" : "coins"}`;
}

export function signedCoins(n: number): string {
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n).toLocaleString("en-GB")}`;
}

export const BET_STATUS: Record<BetStatus, { label: string; tone: string }> = {
  PENDING: { label: "Pending", tone: "text-accent-2" },
  WON: { label: "Won", tone: "text-ok" },
  LOST: { label: "Lost", tone: "text-bad" },
  VOID: { label: "Refunded", tone: "text-muted" },
};

export const MARKET_STATUS: Record<MarketStatus, string> = {
  DRAFT: "Draft",
  OPEN: "Open",
  SUSPENDED: "Paused",
  CLOSED: "Closed",
  SETTLED: "Settled",
  VOID: "Void",
};

/** "Closes in 2h 05m", "Closes in 45s", or "Closed". */
export function closesIn(closesAt: string, now: number = Date.now()): string {
  const s = Math.floor((new Date(closesAt).getTime() - now) / 1000);
  if (s <= 0) return "Closed";
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `Closes in ${d}d ${h}h`;
  if (h > 0) return `Closes in ${h}h ${String(m).padStart(2, "0")}m`;
  if (m > 0) return `Closes in ${m}m`;
  return `Closes in ${s}s`;
}

export function percent(accuracy: number | null): string {
  return accuracy === null ? "–" : `${Math.round(accuracy * 1000) / 10}%`;
}

/** What each leaderboard tab measures, shown on the page. */
export const METRICS: { key: Metric; label: string; explain: (min: number) => string }[] = [
  { key: "balance", label: "Coins", explain: () => "Coins held now. Everyone started with the same amount, so this is total profit." },
  {
    key: "accuracy",
    label: "Accuracy",
    explain: (min) => `Won ÷ (won + lost). Refunded bets don't count. Shown after ${min} settled predictions.`,
  },
  { key: "wins", label: "Wins", explain: () => "Number of winning predictions." },
];

/** A new key for one tap on Confirm, so a resend is never a second bet. */
export function newKey(): string {
  return crypto.randomUUID();
}

/** Markets grouped under their fixture (or "Season" when they cover more than one match). */
export function byFixture(markets: Market[]): { key: string; title: string; markets: Market[] }[] {
  const groups = new Map<string, { key: string; title: string; markets: Market[] }>();
  for (const m of markets) {
    const key = m.fixture ? `f${m.fixture.id}` : `s${m.season.id}`;
    const title = m.fixture ? m.fixture.title : m.season.name;
    if (!groups.has(key)) groups.set(key, { key, title, markets: [] });
    groups.get(key)!.markets.push(m);
  }
  return [...groups.values()];
}
