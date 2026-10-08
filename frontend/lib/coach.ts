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

export type WeaponClass = "" | "AR" | "SMG" | "SHOTGUN" | "SNIPER" | "MARKSMAN" | "LMG" | "PISTOL" | "MELEE" | "THROWABLE" | "OTHER";

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
