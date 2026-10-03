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
