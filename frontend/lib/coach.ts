// The AI Coach's knowledge base (staff-edited general Free Fire knowledge).

export type KnowledgeKind = "WEAPON" | "ATTACHMENT" | "CHARACTER" | "PET" | "UTILITY" | "MAP" | "ZONE" | "GENERAL";

export const KINDS: { key: KnowledgeKind; label: string }[] = [
  { key: "UTILITY", label: "Utility" },
  { key: "MAP", label: "Maps, drops and routes" },
  { key: "ZONE", label: "Zone" },
  { key: "WEAPON", label: "Weapons" },
  { key: "ATTACHMENT", label: "Attachments" },
  { key: "CHARACTER", label: "Characters" },
  { key: "PET", label: "Pets" },
  { key: "GENERAL", label: "General" },
];

export type KnowledgeEntry = {
  id: number;
  kind: KnowledgeKind;
  title: string;
  body: string;
  data: Record<string, unknown>;
  map: string | null;
  area: number | null;
  area_name: string | null;
  area_status: "CONFIRMED" | "SUGGESTED" | null;
  status: KnowledgeStatus;
  origin: "STAFF" | "RESEARCH";
  sources: KnowledgeSource[];
  patch: string;
  conflicts: string;
  weak_sources: boolean;
  weak_reason: string;
  updated_by: string | null;
  updated_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
};

export type KnowledgeStatus = "DRAFT" | "APPROVED" | "REJECTED";

export type KnowledgeSource = { title?: string; url: string; publisher?: string; published?: string | null; accessed?: string };

/** Which entries a staff filter shows. "WRITE" = no text yet. */
export type ReviewFilter = "ALL" | "DRAFT" | "APPROVED" | "REJECTED" | "WRITE" | "WEAK";

export function matchesReview(e: Pick<KnowledgeEntry, "status" | "body" | "weak_sources">, f: ReviewFilter): boolean {
  if (f === "ALL") return true;
  if (f === "WRITE") return !e.body.trim();
  if (f === "WEAK") return e.weak_sources && e.status !== "REJECTED";
  return e.status === f;
}

/** "Fandom wiki, 2026-09-10" for a source line. */
export function sourceLine(s: KnowledgeSource): string {
  const who = s.publisher || hostOf(s.url);
  const when = s.published ? s.published : s.accessed ? `no date, read ${s.accessed}` : "no date";
  return `${who}, ${when}`;
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export type WeaponClass = "" | "AR" | "SMG" | "SHOTGUN" | "SNIPER" | "MARKSMAN" | "LMG" | "PISTOL" | "MELEE" | "THROWABLE" | "EXPLOSIVE" | "OTHER";

export const WEAPON_CLASSES: { key: WeaponClass; label: string }[] = [
  { key: "", label: "Class..." },
  { key: "AR", label: "Assault rifle" },
  { key: "SMG", label: "SMG" },
  { key: "SHOTGUN", label: "Shotgun" },
  { key: "SNIPER", label: "Sniper" },
  { key: "MARKSMAN", label: "Marksman rifle" },
  { key: "LMG", label: "LMG" },
  { key: "PISTOL", label: "Pistol" },
  { key: "MELEE", label: "Melee" },
  { key: "THROWABLE", label: "Throwable" },
  { key: "EXPLOSIVE", label: "Explosive launcher (M79, grenadier)" },
  { key: "OTHER", label: "Other" },
];

export type WeaponRow = {
  weapon_id: number;
  kills: number;
  knocks: number;
  name: string;
  weapon_class: WeaponClass;
  note: string;
};

/** The data box as text, and back. Returns null when the text isn't a JSON object. */
export function dataText(data: Record<string, unknown>): string {
  return Object.keys(data).length ? JSON.stringify(data, null, 2) : "";
}

export function parseData(text: string): Record<string, unknown> | null {
  if (!text.trim()) return {};
  try {
    const value: unknown = JSON.parse(text);
    return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

export type Fact = {
  id: string;
  topic: string;
  text: string;
  value: number;
  n: number;
  of: number;
  matches: number[];
  map: string | null;
  data: Record<string, unknown>;
};

export type CoachTask = {
  title: string;
  why: string[];
  facts: string[];
  matches: number[];
  /** Written by the AI writer and checked against the facts; missing when the template text stands. */
  advice?: string;
  knowledge?: { id: string; title: string }[];
};

/** Whether the AI writer wrote any of a report's or plan's text. */
export const aiWritten = (writer: string) => writer.includes("gemini:");

export type AiUsage = {
  on: boolean;
  blocked: string | null;
  model: string;
  today: number;
  daily_limit: number;
  per_minute: number;
  month_cost_usd: number;
  monthly_cap_usd: number;
  recent: {
    at: string;
    feature: string;
    model: string;
    ok: boolean;
    error: string;
    items: number;
    kept: number;
    tokens: number;
    cost_usd: number;
  }[];
};
export type CoachChange = { text: string; better: boolean; matches: number[] };
export type ReportMatch = { id: number; label: string; map: string; played_on: string | null };

export type CoachReport = {
  id: number;
  team: string;
  team_slug: string;
  week_start: string;
  matches: ReportMatch[];
  facts: Fact[];
  tasks: CoachTask[];
  changes: CoachChange[];
  writer: string;
  is_published: boolean;
  edited_by: string | null;
  updated_at: string;
};

export const TOPICS: { key: string; label: string }[] = [
  { key: "results", label: "Results" },
  { key: "style", label: "Playstyle" },
  { key: "rotation", label: "Rotations" },
  { key: "position", label: "Position in the zone" },
  { key: "fights", label: "Fights" },
  { key: "deaths", label: "Where you die" },
  { key: "drops", label: "Drops" },
];

/** Facts grouped by topic in reading order; overall facts before per-map ones. */
export function factsByTopic(facts: Fact[]): { key: string; label: string; facts: Fact[] }[] {
  return TOPICS.map((t) => ({
    ...t,
    facts: facts.filter((f) => f.topic === t.key).sort((a, b) => Number(!!a.map) - Number(!!b.map) || (a.map ?? "").localeCompare(b.map ?? "")),
  })).filter((g) => g.facts.length > 0);
}

export function weekLabel(weekStart: string): string {
  const d = new Date(`${weekStart}T00:00:00`);
  return `Week of ${d.toLocaleDateString(undefined, { day: "numeric", month: "short" })}`;
}

export type CoachPlay = CoachTask;
export type HeadToHead = { met: number[]; fights: number; won: number; lost: number; matches: number[] };

export type CounterPlan = {
  team: string;
  opponent: string;
  opponent_slug: string;
  week_start: string;
  matches: ReportMatch[];
  facts: Fact[];
  plays: CoachPlay[];
  head_to_head: HeadToHead;
  writer: string;
  updated_at: string;
};

/** One line on how two teams have done against each other, from the asking team's side. */
export function headToHeadText(h: HeadToHead, opponent: string): string {
  if (h.met.length === 0) return `You haven't played in the same match as ${opponent} yet.`;
  const games = `${h.met.length} match${h.met.length === 1 ? "" : "es"}`;
  if (h.fights === 0) return `You've been in ${games} with ${opponent} but haven't fought them.`;
  return `Against ${opponent}: won ${h.won}, lost ${h.lost} of ${h.fights} fight${h.fights === 1 ? "" : "s"} over ${games}.`;
}

export type RotateRoute = { team: string; match: number; label: string; placement: number; path: number[][][] };
export type RotateDrop = {
  place: string;
  x: number;
  z: number;
  team_matches: number;
  matches: number[];
  avg_placement: number;
  top_finishes: number;
  left_s: number | null;
  inside_s: Record<string, number>;
  advice: string[];
  top_matches: number[];
  routes: RotateRoute[];
};
export type RotationAdvice = {
  map: string;
  name: string;
  matches: { id: number; label: string }[];
  zone_ends: { match: number; label: string; zone: number; x: number; z: number; r: number }[];
  drops: RotateDrop[];
};

// -- After-scrim review ---------------------------------------------------------------------

export type MomentKind = "third_party" | "alone" | "rotating" | "untraded" | "zone" | "fight_won" | "trade";

export type ReviewMoment = {
  kind: MomentKind;
  good: boolean;
  t: number;
  clock: string;
  /** Where "Watch this" opens the replay: a few seconds before the moment. */
  watch_s: number;
  title: string;
  detail: string;
  players: string[];
  opponent: number | null;
};

export type ReviewMatch = {
  id: number;
  number: number;
  label: string;
  map: string | null;
  placement: number;
  kills: number;
  downs_taken: number;
  eliminated_s: number | null;
  eliminated_clock: string | null;
  wiped_by: string | null;
  has_tracks: boolean;
  moments: ReviewMoment[];
};

export type ReviewDay = { id: number; label: string; date: string | null };

export type TeamReview = {
  team: { slug: string; name: string };
  days: ReviewDay[];
  day: ReviewDay | null;
  matches: ReviewMatch[];
};

export const MOMENT_LABELS: Record<MomentKind, string> = {
  third_party: "Third party",
  alone: "Alone",
  rotating: "Rotating",
  untraded: "No trade",
  zone: "Zone",
  fight_won: "Fight won",
  trade: "Trade",
};

/** The session's pattern: which mistakes came back in more than one match, most first. */
export function repeatedMistakes(matches: ReviewMatch[]): { kind: MomentKind; label: string; matches: number }[] {
  const seen = new Map<MomentKind, Set<number>>();
  for (const m of matches) {
    for (const x of m.moments) {
      if (x.good) continue;
      if (!seen.has(x.kind)) seen.set(x.kind, new Set());
      seen.get(x.kind)!.add(m.id);
    }
  }
  return [...seen.entries()]
    .filter(([, ids]) => ids.size >= 2)
    .map(([kind, ids]) => ({ kind, label: MOMENT_LABELS[kind], matches: ids.size }))
    .sort((a, b) => b.matches - a.matches || a.label.localeCompare(b.label));
}

/** "Booyah", or "#4 · out at 15:17 to NOOBZ". */
export function finishText(m: Pick<ReviewMatch, "placement" | "eliminated_clock" | "wiped_by">): string {
  if (m.placement === 1) return "Booyah";
  const out = m.eliminated_clock ? ` · out at ${m.eliminated_clock}${m.wiped_by ? ` to ${m.wiped_by}` : ""}` : "";
  return `#${m.placement}${out}`;
}

// -- Player cards ---------------------------------------------------------------------------

export type PlayerClip = { match: number; label: string; t: number; clock: string; watch_s: number };

export type PlayerRates = { alone: number | null; trade: number | null; far: number | null; first: number | null };

export type PlayerCard = {
  player: number | null;
  name: string;
  matches: number;
  kills: number;
  knocks: number;
  kills_per_match: number;
  downs: number;
  alone_downs: number;
  known_downs: number;
  trades: number;
  trade_chances: number;
  first_downs: number;
  spacing_m: number | null;
  alive_s: number | null;
  alive_clock: string | null;
  rates: PlayerRates;
  weapons: { name: string; kills: number }[];
  utility: { uav?: number; bolt?: number; scan?: number };
  task: { title: string; why: string; clips: PlayerClip[] } | null;
  strengths: string[];
};

export type TeamPlayers = {
  team: { slug: string; name: string };
  period: "30" | "all";
  matches: number;
  pending: number;
  league: PlayerRates;
  players: PlayerCard[];
};

/** "33%", or a dash when there isn't enough data for a rate. */
export function pct(rate: number | null): string {
  return rate == null ? "–" : `${Math.round(rate * 100)}%`;
}

/** How a player's rate compares with the league's, when lower is better (or higher). */
export function versus(rate: number | null, league: number | null, lowerIsBetter: boolean): "better" | "worse" | "even" | null {
  if (rate == null || league == null) return null;
  const diff = lowerIsBetter ? league - rate : rate - league;
  if (diff >= 0.1) return "better";
  if (diff <= -0.1) return "worse";
  return "even";
}

/** "2 UAV · 5 Dinoculars", or "" when none were used. */
export function utilityText(u: PlayerCard["utility"]): string {
  const parts: string[] = [];
  if (u.uav) parts.push(`${u.uav} UAV`);
  if (u.bolt) parts.push(`${u.bolt} Bolt Maker`);
  if (u.scan) parts.push(`${u.scan} Dinoculars`);
  return parts.join(" · ");
}
