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

export type PPlayer = { id: number; name: string; team: PTeam | null };

export type Outcome = { id: number; code: string; label: string; team: PTeam | null; player?: PPlayer | null; odds: string; is_active: boolean };

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
  /** Predictions on it so far: single bets and multiple picks. */
  predictions: number;
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

export type MultiplePick = {
  market: { id: number; title: string; status: MarketStatus; fixture: Fixture | null };
  outcome: { id: number; label: string };
  odds_accepted: string;
  status: BetStatus;
  dead_heat: number;
};

/** Several picks in one bet, the odds multiplied (an accumulator). */
export type Multiple = {
  id: string;
  stake: number;
  odds: string;
  potential_return: number;
  potential_profit: number;
  capped: boolean;
  payout: number | null;
  status: BetStatus;
  placed_at: string;
  settled_at: string | null;
  picks: MultiplePick[];
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
/** Picks in one multiple, and the most a multiple can pay (the server's settings). */
export const MAX_PICKS = 8;
export const MAX_RETURN = 50000;

/** Odds "2.55" as whole hundredths (255), so sums stay exact. */
function hundredths(odds: string): number {
  const [whole, frac = ""] = odds.split(".");
  return Number(whole) * 100 + Number((frac + "00").slice(0, 2));
}

/** Stake x odds, rounded down to a whole coin: the same sum the server makes. */
export function totalReturn(stake: number, odds: string): number {
  return Math.floor((stake * hundredths(odds)) / 100);
}

export type OddsFormat = "decimal" | "fractional";

function gcd(a: number, b: number): number {
  return b === 0 ? a : gcd(b, a % b);
}

/** Decimal odds as a bookmaker's fraction: profit over stake, so 3.25 is 9/4 and 2.00 is
 * Evens. Works for combined odds too (big numbers stay whole: 24.05 is 2305/100 = 461/20). */
export function fractional(odds: string): string {
  const [whole, frac = ""] = odds.split(".");
  const top = BigInt(whole) * BigInt(100) + BigInt((frac + "00").slice(0, 2)) - BigInt(100);
  if (top <= BigInt(0)) return "0/1";
  if (top === BigInt(100)) return "Evens";
  // Reduce by what top shares with 100 (that is all a gcd with 100 can be).
  const div = gcd(Number(top % BigInt(100)), 100);
  return `${top / BigInt(div)}/${100 / div}`;
}

/** Odds as the player chose to see them. The server always works in decimal. */
export function showOdds(odds: string, format: OddsFormat): string {
  return format === "fractional" ? fractional(odds) : odds;
}

/** Every pick's odds multiplied, rounded down to 2 decimals, for showing. */
export function combinedOdds(odds: string[]): string {
  let total = BigInt(1);
  for (const o of odds) total *= BigInt(hundredths(o));
  const scaled = total / BigInt(100) ** BigInt(Math.max(odds.length - 1, 0)); // in hundredths
  const whole = scaled / BigInt(100);
  return `${whole}.${String(scaled % BigInt(100)).padStart(2, "0")}`;
}

/** What a multiple returns if every pick wins: stake x every odds, rounded down, capped.
 * Whole-number maths, so it matches the server to the coin. */
export function multipleReturn(stake: number, odds: string[]): number {
  let top = BigInt(stake);
  for (const o of odds) top *= BigInt(hundredths(o));
  const coinsBack = top / BigInt(100) ** BigInt(odds.length);
  return coinsBack > BigInt(MAX_RETURN) ? MAX_RETURN : Number(coinsBack);
}

/** One pick on the bet slip, with what's needed to show it and check it. */
export type SlipPick = {
  market: number;
  marketTitle: string;
  fixture: Pick<Fixture, "id" | "title" | "date" | "session" | "match_number"> | null;
  season: number;
  outcome: number;
  label: string;
  odds: string;
};

/** True when two picks can't be in one multiple: the same match, or a whole-session
 * market and anything in that session. The server checks this again. */
export function slipClash(a: SlipPick, b: SlipPick): boolean {
  const x = a.fixture;
  const y = b.fixture;
  if (!x || !y || a.season !== b.season || x.date !== y.date || x.session !== y.session) return false;
  return x.match_number === null || y.match_number === null || x.match_number === y.match_number;
}

/** Why the slip can't be placed as it is (beyond the stake), or null. */
export function slipProblem(picks: SlipPick[]): string | null {
  if (picks.length === 0) return "Tap odds to add picks.";
  if (picks.length > MAX_PICKS) return `A multiple can have at most ${MAX_PICKS} picks.`;
  for (let i = 0; i < picks.length; i++)
    for (const other of picks.slice(i + 1))
      if (slipClash(picks[i], other)) return `${picks[i].marketTitle} and ${other.marketTitle} are on the same match, so they can't go in one multiple.`;
  return null;
}

/** The slip pick for a choice on a market. */
export function toPick(m: Market, o: Outcome): SlipPick {
  const f = m.fixture;
  return {
    market: m.id,
    marketTitle: m.title,
    fixture: f ? { id: f.id, title: f.title, date: f.date, session: f.session, match_number: f.match_number } : null,
    season: m.season.id,
    outcome: o.id,
    label: o.label,
    odds: o.odds,
  };
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
  | "TOTAL_KILLS"
  | "KILLS_HANDICAP"
  | "POINTS_HANDICAP"
  | "FINISH_BAND"
  | "FIRST_OUT"
  | "FIRST_BLOOD"
  | "PLAYER_KILLS"
  | "TOP_FRAGGER"
  | "PLAYER_H2H"
  | "FIRST_DEATH"
  | "PLAYER_DAMAGE"
  | "SESSION_WINNER"
  | "MOST_BOOYAHS"
  | "SESSION_KILLS"
  | "SESSION_H2H"
  | "SESSION_FRAGGER"
  | "OVERALL_WINNER"
  | "OVERALL_TOP_N"
  | "SEASON_FRAGGER"
  | "RANGE_WINNER"
  | "RANGE_TOP_N"
  | "RANGE_FRAGGER";

/** What a market is about: one match, a whole session, or the whole season (no fixture). */
export type Scope = "match" | "session" | "season";

/** A line staff type in: its range, what it's called and where it starts. */
export type Line = { min: number; max: number; label: string; start: number };

export type CategorySpec = {
  key: Category;
  label: string;
  /** How many teams and players to pick: [at least, at most (null: any)]. */
  teams: [number, number | null];
  players: [number, number | null];
  line: Line | null;
  scope: Scope;
  /** Covers the matches played from one date to another (both included). */
  dates?: boolean;
};

const NONE: [number, number | null] = [0, 0];
const KILLS_LINE: Line = { min: 1, max: 60, label: "Kills line", start: 10 };

export const CATEGORIES: CategorySpec[] = [
  { key: "BOOYAH", label: "Booyah (match winner)", teams: [2, null], players: NONE, line: null, scope: "match" },
  { key: "TOP_N", label: "Team finishes top N (yes/no)", teams: [1, 1], players: NONE, line: null, scope: "match" },
  { key: "FINISH_BAND", label: "Finishing position (1st, 2nd-3rd, 4th-6th, 7th+)", teams: [1, 1], players: NONE, line: null, scope: "match" },
  { key: "H2H_PLACEMENT", label: "Head-to-head: finishes higher", teams: [2, 2], players: NONE, line: null, scope: "match" },
  { key: "H2H_KILLS", label: "Head-to-head: more kills (tie refunds)", teams: [2, 2], players: NONE, line: null, scope: "match" },
  { key: "H2H_POINTS", label: "Head-to-head: more points (tie refunds)", teams: [2, 2], players: NONE, line: null, scope: "match" },
  {
    key: "KILLS_HANDICAP",
    label: "Kills handicap (first team gives a head start)",
    teams: [2, 2],
    players: NONE,
    line: { min: 1, max: 30, label: "Handicap (kills)", start: 3 },
    scope: "match",
  },
  {
    key: "POINTS_HANDICAP",
    label: "Points handicap (first team gives a head start)",
    teams: [2, 2],
    players: NONE,
    line: { min: 1, max: 100, label: "Handicap (points)", start: 5 },
    scope: "match",
  },
  { key: "TEAM_KILLS", label: "Team kills (over/under a line)", teams: [1, 1], players: NONE, line: KILLS_LINE, scope: "match" },
  {
    key: "TOTAL_KILLS",
    label: "Total kills in the match (over/under)",
    teams: NONE,
    players: NONE,
    line: { min: 1, max: 300, label: "Kills line", start: 70 },
    scope: "match",
  },
  { key: "FIRST_OUT", label: "First team out", teams: [2, null], players: NONE, line: null, scope: "match" },
  { key: "FIRST_BLOOD", label: "First blood (team with the first kill)", teams: [2, null], players: NONE, line: null, scope: "match" },
  {
    key: "PLAYER_KILLS",
    label: "Player kills (over/under)",
    teams: NONE,
    players: [1, 1],
    line: { min: 1, max: 30, label: "Kills line", start: 3 },
    scope: "match",
  },
  {
    key: "PLAYER_DAMAGE",
    label: "Player damage (over/under)",
    teams: NONE,
    players: [1, 1],
    line: { min: 100, max: 20000, label: "Damage line", start: 1000 },
    scope: "match",
  },
  { key: "TOP_FRAGGER", label: "Top fragger (ties share)", teams: NONE, players: [2, null], line: null, scope: "match" },
  { key: "PLAYER_H2H", label: "Player head-to-head: more kills (tie refunds)", teams: NONE, players: [2, 2], line: null, scope: "match" },
  { key: "FIRST_DEATH", label: "First player to die (ties share)", teams: NONE, players: [2, null], line: null, scope: "match" },
  { key: "SESSION_WINNER", label: "Session winner (most points)", teams: [2, null], players: NONE, line: null, scope: "session" },
  { key: "MOST_BOOYAHS", label: "Most Booyahs in the session (ties share)", teams: [2, null], players: NONE, line: null, scope: "session" },
  {
    key: "SESSION_KILLS",
    label: "Team kills in the session (over/under)",
    teams: [1, 1],
    players: NONE,
    line: { min: 1, max: 200, label: "Kills line", start: 40 },
    scope: "session",
  },
  { key: "SESSION_H2H", label: "Session head-to-head: more points (tie refunds)", teams: [2, 2], players: NONE, line: null, scope: "session" },
  { key: "SESSION_FRAGGER", label: "Session top fragger (ties share)", teams: NONE, players: [2, null], line: null, scope: "session" },
  { key: "OVERALL_WINNER", label: "Overall winner (season table)", teams: [2, null], players: NONE, line: null, scope: "season" },
  { key: "OVERALL_TOP_N", label: "Overall top N (yes/no)", teams: [1, 1], players: NONE, line: null, scope: "season" },
  { key: "SEASON_FRAGGER", label: "Season top fragger (ties share)", teams: NONE, players: [2, null], line: null, scope: "season" },
  { key: "RANGE_WINNER", label: "Most points between two dates (ties share)", teams: [2, null], players: NONE, line: null, scope: "season", dates: true },
  { key: "RANGE_TOP_N", label: "Top N between two dates (yes/no)", teams: [1, 1], players: NONE, line: null, scope: "season", dates: true },
  { key: "RANGE_FRAGGER", label: "Top fragger between two dates (ties share)", teams: NONE, players: [2, null], line: null, scope: "season", dates: true },
];

/** Markets where those level on the result share the win (a dead heat). */
export const SHARED_WIN = new Set<string>([
  "SESSION_WINNER",
  "MOST_BOOYAHS",
  "OVERALL_WINNER",
  "TOP_FRAGGER",
  "FIRST_DEATH",
  "SESSION_FRAGGER",
  "SEASON_FRAGGER",
  "RANGE_WINNER",
  "RANGE_FRAGGER",
]);

/** How each kind of market is settled, in one line for players. */
export const RULES: Partial<Record<Category, string>> = {
  BOOYAH: "Settled on the team that finishes 1st. A listed team that doesn't play is refunded.",
  TOP_N: "Settled on the team's final position in the match.",
  FINISH_BAND: "Settled on the team's final position in the match. Refunded if the team doesn't play.",
  H2H_PLACEMENT: "The team that finishes higher wins. Refunded if either team doesn't play.",
  H2H_KILLS: "The team with more kills wins. A tie is refunded.",
  H2H_POINTS: "The team with more points wins. A tie is refunded.",
  KILLS_HANDICAP: "The handicap is applied to the final kills. The half-kill means there's never a tie.",
  POINTS_HANDICAP: "The handicap is applied to the final points. The half-point means there's never a tie.",
  TEAM_KILLS: "Settled on the team's kills on the final scoreboard.",
  TOTAL_KILLS: "Every team's kills on the final scoreboard, added up.",
  FIRST_OUT: "The team that finishes last is the first one out.",
  FIRST_BLOOD: "The team of the player who gets the first kill. Kills on a team-mate don't count.",
  PLAYER_KILLS: "Settled on the player's kills on the final scoreboard. Refunded if they don't play.",
  PLAYER_DAMAGE: "Settled on the damage the player deals to enemies. Refunded if they don't play or the match has no damage figures.",
  TOP_FRAGGER: "The player with the most kills in the match. A listed player who doesn't play is refunded.",
  PLAYER_H2H: "The player with more kills wins. A tie, or either player not playing, is refunded.",
  FIRST_DEATH: "The first player in the match to die, from any cause.",
  SESSION_KILLS: "The team's kills in every match of the session, added up.",
  SESSION_H2H: "The team with more points over the session wins. A tie, or either team not playing, is refunded.",
  SESSION_FRAGGER: "The player with the most kills over the whole session. A listed player who doesn't play is refunded.",
  SEASON_FRAGGER: "The player with the most kills over the season. A listed player who doesn't play is refunded.",
  RANGE_WINNER: "A table of only the matches between the two dates, scored like the league table. Settled after the last date.",
  RANGE_TOP_N: "The team's position in a table of only the matches between the two dates. Settled after the last date.",
  RANGE_FRAGGER: "The player with the most kills between the two dates. Settled after the last date.",
};

export function spec(category: Category): CategorySpec {
  return CATEGORIES.find((c) => c.key === category)!;
}

type Named = { id: number; name: string };

/** "19.5" for a line of 20: the half-point that keeps over/under from tying. */
const half = (line: number) => String(line - 0.5);

/** The outcome codes the server will create, in order, so staff can give odds for each. */
export function outcomeCodes(category: Category, teams: Named[], n = 3, line = 10, players: Named[] = []): { code: string; label: string }[] {
  const name = teams[0]?.name ?? "Team";
  const who = players[0]?.name ?? "Player";
  switch (category) {
    case "TOP_N":
    case "OVERALL_TOP_N":
    case "RANGE_TOP_N":
      return [
        { code: "yes", label: `Yes, ${name} top ${n}` },
        { code: "no", label: `No, ${name} outside top ${n}` },
      ];
    case "TEAM_KILLS":
      return [
        { code: "yes", label: `${name}: ${line} or more kills` },
        { code: "no", label: `${name}: ${line - 1} or fewer kills` },
      ];
    case "SESSION_KILLS":
      return [
        { code: "yes", label: `${name}: over ${half(line)} kills` },
        { code: "no", label: `${name}: under ${half(line)} kills` },
      ];
    case "TOTAL_KILLS":
      return [
        { code: "yes", label: `Over ${half(line)} kills` },
        { code: "no", label: `Under ${half(line)} kills` },
      ];
    case "KILLS_HANDICAP":
    case "POINTS_HANDICAP": {
      const what = category === "KILLS_HANDICAP" ? "kills" : "points";
      const [a, b] = teams;
      if (!a || !b) return [];
      return [
        { code: `team:${a.id}`, label: `${a.name} -${half(line)} ${what}` },
        { code: `team:${b.id}`, label: `${b.name} +${half(line)} ${what}` },
      ];
    }
    case "FINISH_BAND":
      if (!teams[0]) return [];
      return [
        { code: "band:1", label: `${name}: 1st` },
        { code: "band:2", label: `${name}: 2nd-3rd` },
        { code: "band:4", label: `${name}: 4th-6th` },
        { code: "band:7", label: `${name}: 7th or lower` },
      ];
    case "PLAYER_KILLS":
    case "PLAYER_DAMAGE": {
      const what = category === "PLAYER_KILLS" ? "kills" : "damage";
      if (!players[0]) return [];
      return [
        { code: "yes", label: `${who}: over ${half(line)} ${what}` },
        { code: "no", label: `${who}: under ${half(line)} ${what}` },
      ];
    }
    case "TOP_FRAGGER":
    case "PLAYER_H2H":
    case "FIRST_DEATH":
    case "SESSION_FRAGGER":
    case "SEASON_FRAGGER":
    case "RANGE_FRAGGER":
      return players.map((p) => ({ code: `player:${p.id}`, label: p.name }));
    default:
      return teams.map((t) => ({ code: `team:${t.id}`, label: t.name }));
  }
}

/** "19 Oct" for "2026-10-19" (the day as written, whatever the time zone). */
export function shortDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${d} ${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m - 1]}`;
}

/** Why a from/to date pair doesn't work for a date-range market, or null. */
export function datesProblem(from: string, to: string): string | null {
  const day = /^\d{4}-\d{2}-\d{2}$/;
  if (!day.test(from) || !day.test(to)) return "Pick both dates.";
  const days = (Date.parse(to) - Date.parse(from)) / 864e5 + 1;
  if (days < 1) return "The end date is before the start date.";
  if (days > MAX_RANGE_DAYS) return `At most ${MAX_RANGE_DAYS} days.`;
  return null;
}

/** The longest date range a market can cover (the server's MAX_RANGE_DAYS). */
export const MAX_RANGE_DAYS = 62;

/** A starting title for a new market. */
export function defaultTitle(
  category: Category,
  teams: { name: string }[],
  n = 3,
  matchNumber: number | null = null,
  line = 10,
  players: { name: string }[] = [],
  dates: { from: string; to: string } | null = null,
): string {
  const where = matchNumber ? ` · Match ${matchNumber}` : "";
  const span = dates ? ` · ${shortDate(dates.from)} to ${shortDate(dates.to)}` : "";
  const [a, b] = teams.map((t) => t.name);
  const [p, q] = players.map((x) => x.name);
  switch (category) {
    case "BOOYAH":
      return `Booyah${where}`;
    case "TOP_N":
      return `${a ?? "Team"} top ${n}${where}`;
    case "FINISH_BAND":
      return `${a ?? "Team"} finishing position${where}`;
    case "H2H_PLACEMENT":
      return `${a ?? "?"} v ${b ?? "?"}: finishes higher${where}`;
    case "H2H_KILLS":
      return `${a ?? "?"} v ${b ?? "?"}: more kills${where}`;
    case "H2H_POINTS":
      return `${a ?? "?"} v ${b ?? "?"}: more points${where}`;
    case "KILLS_HANDICAP":
      return `${a ?? "?"} v ${b ?? "?"}: kills handicap${where}`;
    case "POINTS_HANDICAP":
      return `${a ?? "?"} v ${b ?? "?"}: points handicap${where}`;
    case "TEAM_KILLS":
      return `${a ?? "Team"}: ${line}+ kills${where}`;
    case "TOTAL_KILLS":
      return `Total kills: over/under ${half(line)}${where}`;
    case "FIRST_OUT":
      return `First team out${where}`;
    case "FIRST_BLOOD":
      return `First blood${where}`;
    case "PLAYER_KILLS":
      return `${p ?? "Player"}: over/under ${half(line)} kills${where}`;
    case "PLAYER_DAMAGE":
      return `${p ?? "Player"}: over/under ${half(line)} damage${where}`;
    case "TOP_FRAGGER":
      return `Top fragger${where}`;
    case "PLAYER_H2H":
      return `${p ?? "?"} v ${q ?? "?"}: more kills${where}`;
    case "FIRST_DEATH":
      return `First player to die${where}`;
    case "SESSION_WINNER":
      return "Session winner";
    case "MOST_BOOYAHS":
      return "Most Booyahs in the session";
    case "OVERALL_WINNER":
      return "Overall winner";
    case "OVERALL_TOP_N":
      return `${a ?? "Team"} overall top ${n}`;
    case "SESSION_KILLS":
      return `${a ?? "Team"}: over/under ${half(line)} kills in the session`;
    case "SESSION_H2H":
      return `${a ?? "?"} v ${b ?? "?"}: more points in the session`;
    case "SESSION_FRAGGER":
      return "Session top fragger";
    case "SEASON_FRAGGER":
      return "Season top fragger";
    case "RANGE_WINNER":
      return `Most points${span}`;
    case "RANGE_TOP_N":
      return `${a ?? "Team"} top ${n}${span}`;
    case "RANGE_FRAGGER":
      return `Top fragger${span}`;
  }
}

/** The market types that fit a fixture: one match, a whole session (no match number), or none. */
export function categoriesFor(scope: Scope) {
  return CATEGORIES.filter((c) => c.scope === scope);
}

/** A line as staff type it: a whole number in the market type's range (1 to 60 for team kills). */
export function lineProblem(text: string, category: Category = "TEAM_KILLS"): string | null {
  const { min, max } = spec(category).line ?? KILLS_LINE;
  return /^\d+$/.test(text.trim()) && Number(text) >= min && Number(text) <= max ? null : `A whole number from ${min} to ${max}.`;
}

function pickProblem([min, max]: [number, number | null], count: number, what: string): string | null {
  if (count < min) return `Pick at least ${min} ${what}${min > 1 ? "s" : ""}.`;
  if (max !== null && count > max) return max === 0 ? `This type has no ${what}s.` : `Pick exactly ${max} ${what}${max > 1 ? "s" : ""}.`;
  return null;
}

/** Why the team picks don't fit the market type, or null. */
export function teamsProblem(category: Category, count: number): string | null {
  return pickProblem(spec(category).teams, count, "team");
}

/** Why the player picks don't fit the market type, or null. */
export function playersProblem(category: Category, count: number): string | null {
  return pickProblem(spec(category).players, count, "player");
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
