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

// -- staff ---------------------------------------------------------------------------------------

export type Category =
  | "BOOYAH"
  | "TOP_N"
  | "H2H_PLACEMENT"
  | "H2H_KILLS"
  | "H2H_POINTS"
  | "TEAM_KILLS"
  | "SESSION_WINNER"
  | "MOST_BOOYAHS"
  | "OVERALL_WINNER"
  | "OVERALL_TOP_N";

/** What a market is about: one match, a whole session, or the whole season (no fixture). */
export type Scope = "match" | "session" | "season";

export const CATEGORIES: { key: Category; label: string; teams: [number, number | null]; scope: Scope }[] = [
  { key: "BOOYAH", label: "Booyah (match winner)", teams: [2, null], scope: "match" },
  { key: "TOP_N", label: "Team finishes top N (yes/no)", teams: [1, 1], scope: "match" },
  { key: "H2H_PLACEMENT", label: "Head-to-head: finishes higher", teams: [2, 2], scope: "match" },
  { key: "H2H_KILLS", label: "Head-to-head: more kills (tie refunds)", teams: [2, 2], scope: "match" },
  { key: "H2H_POINTS", label: "Head-to-head: more points (tie refunds)", teams: [2, 2], scope: "match" },
  { key: "TEAM_KILLS", label: "Team kills (over/under a line)", teams: [1, 1], scope: "match" },
  { key: "SESSION_WINNER", label: "Session winner (most points)", teams: [2, null], scope: "session" },
  { key: "MOST_BOOYAHS", label: "Most Booyahs in the session (ties share)", teams: [2, null], scope: "session" },
  { key: "OVERALL_WINNER", label: "Overall winner (season table)", teams: [2, null], scope: "season" },
  { key: "OVERALL_TOP_N", label: "Overall top N (yes/no)", teams: [1, 1], scope: "season" },
];

/** The outcome codes the server will create, in order, so staff can give odds for each. */
export function outcomeCodes(category: Category, teams: { id: number; name: string }[], n = 3, line = 10): { code: string; label: string }[] {
  const name = teams[0]?.name ?? "Team";
  if (category === "TOP_N" || category === "OVERALL_TOP_N") {
    return [
      { code: "yes", label: `Yes, ${name} top ${n}` },
      { code: "no", label: `No, ${name} outside top ${n}` },
    ];
  }
  if (category === "TEAM_KILLS") {
    return [
      { code: "yes", label: `${name}: ${line} or more kills` },
      { code: "no", label: `${name}: ${line - 1} or fewer kills` },
    ];
  }
  return teams.map((t) => ({ code: `team:${t.id}`, label: t.name }));
}

/** A starting title for a new market. */
export function defaultTitle(category: Category, teams: { name: string }[], n = 3, matchNumber: number | null = null, line = 10): string {
  const where = matchNumber ? ` · Match ${matchNumber}` : "";
  const [a, b] = teams.map((t) => t.name);
  switch (category) {
    case "BOOYAH":
      return `Booyah${where}`;
    case "TOP_N":
      return `${a ?? "Team"} top ${n}${where}`;
    case "H2H_PLACEMENT":
      return `${a ?? "?"} v ${b ?? "?"}: finishes higher${where}`;
    case "H2H_KILLS":
      return `${a ?? "?"} v ${b ?? "?"}: more kills${where}`;
    case "H2H_POINTS":
      return `${a ?? "?"} v ${b ?? "?"}: more points${where}`;
    case "TEAM_KILLS":
      return `${a ?? "Team"}: ${line}+ kills${where}`;
    case "SESSION_WINNER":
      return "Session winner";
    case "MOST_BOOYAHS":
      return "Most Booyahs in the session";
    case "OVERALL_WINNER":
      return "Overall winner";
    case "OVERALL_TOP_N":
      return `${a ?? "Team"} overall top ${n}`;
  }
}

/** The market types that fit a fixture: one match, a whole session (no match number), or none. */
export function categoriesFor(scope: Scope) {
  return CATEGORIES.filter((c) => c.scope === scope);
}

/** A kills line as staff type it: a whole number from 1 to 60. */
export function lineProblem(text: string): string | null {
  return /^\d+$/.test(text.trim()) && Number(text) >= 1 && Number(text) <= 60 ? null : "A whole number from 1 to 60.";
}

/** Why the team picks don't fit the market type, or null. */
export function teamsProblem(category: Category, count: number): string | null {
  const [min, max] = CATEGORIES.find((c) => c.key === category)!.teams;
  if (count < min) return `Pick at least ${min} team${min > 1 ? "s" : ""}.`;
  if (max !== null && count > max) return `Pick exactly ${max} team${max > 1 ? "s" : ""}.`;
  return null;
}

/** Odds as staff type them: 1.01 to 1000, at most 2 decimals. */
export function oddsProblem(text: string): string | null {
  if (!/^\d+(\.\d{1,2})?$/.test(text.trim())) return "Use a number like 2.50.";
  const n = Number(text);
  if (n < 1.01 || n > 1000) return "Between 1.01 and 1000.";
  return null;
}

/** ISO time to the value a datetime-local input wants (local time). */
export function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}
