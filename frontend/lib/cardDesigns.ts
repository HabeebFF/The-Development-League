// Card designs bought in the shop with DC. A design is a choice of parts (palette, pattern,
// effect) that the site draws; keep the keys in step with backend apps/shop/looks.py.
// A design changes only how a card looks, never its numbers.

export type DesignParts = { palette: string; pattern: string; effect: string };

export type CardDesign = {
  id: number;
  slug: string;
  name: string;
  rarity: "COMMON" | "RARE" | "EPIC" | "LEGENDARY" | "VINTAGE" | "DIAMOND" | "MYTHIC";
  parts: DesignParts;
  /** This copy's number for a limited design ("#7 of 20"). */
  copy_number: number | null;
  copies: number | null;
};

export type ShopDesign = CardDesign & {
  price: number;
  rarity_label: string;
  sold: number;
  left: number | null;
  sale_ends: string | null;
  available: boolean;
  owned: boolean;
  equipped: boolean;
};

/** [top, bottom, ink, line, glow (r g b)] like the tier colours. */
export const PALETTES: Record<string, [string, string, string, string, string]> = {
  carbon: ["#2a2d36", "#0b0c10", "#f2f3f7", "#8a8f9c", "160 165 180"],
  ocean: ["#1d6fb8", "#071a33", "#eaf5ff", "#7cc4ff", "56 160 255"],
  gold: ["#ffcf5a", "#7a4a06", "#1d1405", "#fff1b8", "245 165 36"],
  cyan: ["#0b2a33", "#030b10", "#e6fdff", "#22e3ff", "34 227 255"],
  crimson: ["#b3122e", "#2a0309", "#fff0f2", "#ff6b81", "255 60 90"],
  emerald: ["#14935f", "#03251a", "#ecfff6", "#5ff2b0", "60 230 160"],
  violet: ["#6b2bd9", "#14052e", "#f4ecff", "#c49bff", "168 110 255"],
  lava: ["#ff6a1a", "#2a0600", "#fff3e6", "#ffb35a", "255 100 30"],
  holo: ["#c9d6ff", "#6f7fb8", "#10142a", "#ffffff", "200 210 255"],
  champion: ["#1a1206", "#050302", "#ffe7a3", "#f5b82e", "245 184 46"],
  vintage: ["#e6d3a8", "#7a5a34", "#2b1b0c", "#fff4d6", "214 176 112"],
  diamond: ["#f2fbff", "#8fb8dc", "#0b1a2a", "#ffffff", "190 232 255"],
  // Player shop collection.
  steel: ["#e4e8ee", "#5d6573", "#0d1016", "#ffffff", "210 218 230"],
  gunmetal: ["#3b4049", "#0b0d11", "#f6e7c1", "#f5b82e", "245 184 46"],
  // "team" is the player's own team colour (see designColors); this is the fallback.
  team: ["#2a3550", "#07090f", "#f2f4fa", "#9fb2e0", "150 170 230"],
  neon: ["#0b1220", "#020409", "#e6fdff", "#22e3ff", "34 227 255"],
  sniper: ["#15291d", "#030a06", "#eaffee", "#5cff8f", "92 255 143"],
  ember: ["#3d1206", "#0a0201", "#fff2e2", "#ff8a3d", "255 122 40"],
  rage: ["#520a14", "#0b0103", "#fff0f1", "#ff3b4f", "255 59 79"],
  smoke: ["#3a4048", "#0d0f12", "#f3f6f0", "#b8f25c", "184 242 92"],
  foil: ["#1c1f33", "#07080f", "#ffffff", "#e9e4ff", "205 195 255"],
  zone: ["#1c0b33", "#05020c", "#fff6e8", "#7fb2ff", "110 160 255"],
  storm: ["#1d2c40", "#03060b", "#eaf4ff", "#a6d6ff", "140 200 255"],
  booyah: ["#3b2804", "#0b0702", "#fff4c8", "#ffd34d", "255 200 60"],
  phoenix: ["#5c1500", "#0c0200", "#fff5de", "#ffb02e", "255 140 30"],
  void: ["#16072b", "#020006", "#f5ecff", "#c084fc", "176 110 255"],
};

/** Tailwind-free CSS backgrounds, layered over the palette gradient. */
export const PATTERNS: Record<string, string> = {
  none: "none",
  carbon:
    "repeating-linear-gradient(45deg, rgb(255 255 255 / 0.05) 0 3px, transparent 3px 6px), repeating-linear-gradient(-45deg, rgb(0 0 0 / 0.25) 0 3px, transparent 3px 6px)",
  lines: "repeating-linear-gradient(115deg, rgb(255 255 255 / 0.09) 0 2px, transparent 2px 18px)",
  hex: "radial-gradient(circle at 50% 50%, rgb(255 255 255 / 0.1) 0 18%, transparent 19%) 0 0 / 1.2em 1.04em, radial-gradient(circle at 50% 50%, rgb(255 255 255 / 0.1) 0 18%, transparent 19%) 0.6em 0.52em / 1.2em 1.04em",
  circuit:
    "linear-gradient(90deg, rgb(34 227 255 / 0.12) 1px, transparent 1px) 0 0 / 1.5em 1.5em, linear-gradient(0deg, rgb(34 227 255 / 0.12) 1px, transparent 1px) 0 0 / 1.5em 1.5em",
  flames:
    "radial-gradient(ellipse 30% 55% at 20% 105%, rgb(255 140 30 / 0.55), transparent 70%), radial-gradient(ellipse 30% 60% at 55% 108%, rgb(255 90 20 / 0.5), transparent 70%), radial-gradient(ellipse 28% 50% at 85% 105%, rgb(255 180 40 / 0.5), transparent 70%)",
  // An old printed card: speckles, a worn edge and a faded stripe.
  paper:
    "radial-gradient(circle at 20% 30%, rgb(90 60 20 / 0.12) 0 1px, transparent 2px) 0 0 / 0.7em 0.9em, radial-gradient(circle at 70% 60%, rgb(90 60 20 / 0.1) 0 1px, transparent 2px) 0 0 / 1.1em 0.8em, radial-gradient(ellipse at 50% 45%, transparent 55%, rgb(70 40 10 / 0.45) 100%), linear-gradient(0deg, transparent 62%, rgb(120 30 20 / 0.18) 62% 66%, transparent 66%)",
  // Cut-stone facets.
  // Brushed metal: fine horizontal grain.
  brushed:
    "repeating-linear-gradient(0deg, rgb(255 255 255 / 0.06) 0 1px, transparent 1px 3px), repeating-linear-gradient(0deg, rgb(0 0 0 / 0.06) 0 1px, transparent 1px 5px)",
  // A sniper scope's range marks.
  scope:
    "radial-gradient(circle at 66% 26%, transparent 0 2.6em, rgb(92 255 143 / 0.28) 2.6em 2.68em, transparent 2.7em 3.9em, rgb(92 255 143 / 0.16) 3.9em 3.96em, transparent 4em), repeating-linear-gradient(0deg, rgb(92 255 143 / 0.05) 0 1px, transparent 1px 4px)",
  facets:
    "conic-gradient(from 30deg at 50% 38%, rgb(255 255 255 / 0.55), rgb(160 200 240 / 0.15) 15%, rgb(255 255 255 / 0.4) 30%, rgb(120 170 220 / 0.2) 45%, rgb(255 255 255 / 0.5) 60%, rgb(150 200 255 / 0.15) 75%, rgb(255 255 255 / 0.45) 90%, rgb(255 255 255 / 0.55))",
};

export const RARITY_COLORS: Record<CardDesign["rarity"], string> = {
  COMMON: "#a0a6b4",
  RARE: "#38bdf8",
  EPIC: "#a855f7",
  LEGENDARY: "#f5b82e",
  VINTAGE: "#d9b779",
  DIAMOND: "#bfe9ff",
  MYTHIC: "#ff3d7f",
};

export const RARITY_LABELS: Record<CardDesign["rarity"], string> = {
  COMMON: "Common",
  RARE: "Rare",
  EPIC: "Epic",
  LEGENDARY: "Legendary",
  VINTAGE: "Vintage",
  DIAMOND: "Diamond",
  MYTHIC: "Mythic",
};

/** The design's colours, or null for an unknown palette (the card then stays plain).
 *  The "team" palette paints the card in the player's own team colour. */
export function designColors(design: CardDesign | null | undefined, teamColor?: string | null) {
  if (!design) return null;
  const p = PALETTES[design.parts.palette];
  if (!p) return null;
  const [top, bottom, ink, line, glow] = p;
  if (design.parts.palette === "team" && teamColor && /^#[0-9a-f]{6}$/i.test(teamColor)) {
    const rgb = [1, 3, 5].map((i) => parseInt(teamColor.slice(i, i + 2), 16)).join(" ");
    return { top: teamColor, bottom, ink, line: `color-mix(in srgb, ${teamColor} 55%, white)`, glow: rgb };
  }
  return { top, bottom, ink, line, glow };
}

/** What a design's rarity adds on top of its look: a glowing frame and an entrance
 *  animation from Legendary up, and a name aura (on the card and across the site) for Mythic. */
export function designPerks(design: CardDesign | null | undefined) {
  const r = design?.rarity;
  const big = r === "LEGENDARY" || r === "MYTHIC";
  return { frame: big, entrance: big, aura: r === "MYTHIC" };
}

export function copyText(design: CardDesign | null | undefined): string | null {
  if (!design || !design.copies || !design.copy_number) return null;
  return `#${design.copy_number} of ${design.copies}`;
}
