// Card designs bought in the shop with DC. A design is a choice of parts (palette, pattern,
// effect) that the site draws; keep the keys in step with backend apps/shop/looks.py.
// A design changes only how a card looks, never its numbers.

export type DesignParts = { palette: string; pattern: string; effect: string };

export type CardDesign = {
  id: number;
  slug: string;
  name: string;
  rarity: "COMMON" | "RARE" | "EPIC" | "LEGENDARY";
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
};

export const RARITY_COLORS: Record<CardDesign["rarity"], string> = {
  COMMON: "#a0a6b4",
  RARE: "#38bdf8",
  EPIC: "#a855f7",
  LEGENDARY: "#f5b82e",
};

export const RARITY_LABELS: Record<CardDesign["rarity"], string> = {
  COMMON: "Common",
  RARE: "Rare",
  EPIC: "Epic",
  LEGENDARY: "Legendary",
};

/** The design's colours, or null for an unknown palette (the card then stays plain). */
export function designColors(design: CardDesign | null | undefined) {
  if (!design) return null;
  const p = PALETTES[design.parts.palette];
  if (!p) return null;
  const [top, bottom, ink, line, glow] = p;
  return { top, bottom, ink, line, glow };
}

export function copyText(design: CardDesign | null | undefined): string | null {
  if (!design || !design.copies || !design.copy_number) return null;
  return `#${design.copy_number} of ${design.copies}`;
}
