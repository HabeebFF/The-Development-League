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
  updated_by: string | null;
  updated_at: string;
};

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

export type CoachTask = { title: string; why: string[]; facts: string[]; matches: number[] };
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
