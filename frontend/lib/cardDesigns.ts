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
  // Player shop: the 30 art designs (components/league/CardArt.tsx).
  noir: ["#7a6248", "#1c1b1a", "#f6ecd8", "#e0c79a", "214 170 110"],
  vice: ["#3a0f5e", "#0b0418", "#ffffff", "#3ef2e0", "255 79 154"],
  wanted: ["#ecdcb0", "#b38b55", "#2a170a", "#5a3a1a", "214 176 112"],
  comic: ["#ffe14d", "#ff8a2a", "#111111", "#111111", "255 210 60"],
  anime: ["#1b2280", "#05051c", "#ffffff", "#7df9ff", "120 220 255"],
  glitch: ["#160b33", "#03020a", "#f0fbff", "#ff2bd6", "255 43 214"],
  vapor: ["#ffb0dd", "#8fd3f0", "#2a1342", "#ffffff", "255 160 225"],
  graffiti: ["#6e3b2c", "#221310", "#ffffff", "#ffe14d", "255 90 190"],
  dossier: ["#d8c592", "#9c8656", "#1c1a12", "#3b3a2a", "190 170 110"],
  prism: ["#eef1ff", "#9aa3d6", "#11133a", "#ffffff", "200 190 255"],
  blueprint: ["#2361ad", "#0b2b5a", "#ffffff", "#ffffff", "120 180 255"],
  arcade: ["#0b0b33", "#000000", "#ffffff", "#39ff14", "57 255 20"],
  afro: ["#3f0f66", "#0b0219", "#fff3d6", "#f5c542", "245 197 66"],
  lagos: ["#22104a", "#05030d", "#ffffff", "#ffd400", "255 212 0"],
  magma: ["#2b1c1c", "#050202", "#fff1e0", "#ff6a1a", "255 90 20"],
  frost: ["#2f6c96", "#061a2c", "#f2fbff", "#d8f3ff", "170 225 255"],
  chaser: ["#2b3050", "#06070f", "#ffffff", "#c9b8ff", "170 150 255"],
  royal: ["#5c0f26", "#15030a", "#fff0c8", "#e6b84d", "230 184 77"],
  ink: ["#f3ecdc", "#d3c4a2", "#141210", "#141210", "200 40 40"],
  steam: ["#5e3d1e", "#1a0f06", "#fbe9c6", "#d79a4a", "215 154 74"],
  station: ["#0b1830", "#010308", "#e8f6ff", "#5fd4ff", "95 212 255"],
  toxic: ["#1e330b", "#040902", "#f2ffe0", "#b6ff1a", "160 255 30"],
  mirage: ["#e7913f", "#3e1706", "#ffffff", "#ffe0a3", "255 170 80"],
  ruins: ["#3a5233", "#0e1a0c", "#eef6e2", "#c4d39a", "150 200 110"],
  racer: ["#2c2f36", "#08090b", "#ffffff", "#ff2a2a", "255 42 42"],
  classic: ["#2a6fd6", "#0d2a63", "#ffffff", "#ffe066", "120 170 255"],
  glass: ["#1d1433", "#07040f", "#ffffff", "#f4d27a", "150 120 255"],
  assassin: ["#1a1220", "#000000", "#f3e9ee", "#ff1f3d", "255 31 61"],
  dragon: ["#2c0b52", "#030016", "#ffffff", "#ff8bf0", "190 120 255"],
  platinum: ["#d9dee6", "#6f7884", "#0b0e13", "#ffffff", "225 235 250"],
};

/** Tailwind-free CSS backgrounds, layered over the palette gradient. */
/** A small SVG drawn as a repeating background tile. */
const tile = (svg: string, size: string) =>
  `url("data:image/svg+xml,${encodeURIComponent(`<svg xmlns='http://www.w3.org/2000/svg' ${svg}</svg>`)}") 0 0 / ${size}`;

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
  // Player shop art designs.
  grain:
    "radial-gradient(circle at 30% 40%, rgb(0 0 0 / 0.18) 0 1px, transparent 1.5px) 0 0 / 0.31em 0.37em, radial-gradient(circle at 70% 20%, rgb(255 255 255 / 0.08) 0 1px, transparent 1.5px) 0 0 / 0.43em 0.29em",
  halftone:
    "radial-gradient(circle, rgb(220 30 40 / 0.32) 30%, transparent 33%) 0 0 / 0.42em 0.42em, radial-gradient(circle, rgb(220 30 40 / 0.32) 30%, transparent 33%) 0.21em 0.21em / 0.42em 0.42em",
  scanlines: "repeating-linear-gradient(0deg, rgb(0 0 0 / 0.32) 0 1px, transparent 1px 3px)",
  bpgrid:
    "linear-gradient(rgb(255 255 255 / 0.2) 1px, transparent 1px) 0 0 / 2.5em 2.5em, linear-gradient(90deg, rgb(255 255 255 / 0.2) 1px, transparent 1px) 0 0 / 2.5em 2.5em, linear-gradient(rgb(255 255 255 / 0.07) 1px, transparent 1px) 0 0 / 0.5em 0.5em, linear-gradient(90deg, rgb(255 255 255 / 0.07) 1px, transparent 1px) 0 0 / 0.5em 0.5em",
  brick: tile(
    "width='40' height='36'><g fill='rgba(0,0,0,0.38)'><rect y='16' width='40' height='2'/><rect y='34' width='40' height='2'/><rect x='38' width='2' height='16'/><rect x='18' y='18' width='2' height='16'/></g><g fill='rgba(255,255,255,0.07)'><rect width='38' height='2'/><rect y='18' width='18' height='2'/><rect x='20' y='18' width='18' height='2'/></g><g fill='rgba(0,0,0,0.12)'><rect x='4' y='6' width='9' height='5'/><rect x='26' y='24' width='7' height='4'/></g>",
    "2.4em 2.16em",
  ),
  pixel:
    "linear-gradient(rgb(255 255 255 / 0.04) 1px, transparent 1px) 0 0 / 0.3em 0.3em, linear-gradient(90deg, rgb(255 255 255 / 0.04) 1px, transparent 1px) 0 0 / 0.3em 0.3em",
  velvet: tile(
    "width='40' height='56'><g fill='none' stroke='rgba(0,0,0,0.28)' stroke-width='2'><path d='M20 6 C28 14 28 22 20 28 C12 22 12 14 20 6Z'/><path d='M20 28 C26 32 32 30 36 26 M20 28 C14 32 8 30 4 26'/><path d='M0 34 C8 42 8 50 0 56 M40 34 C32 42 32 50 40 56'/></g><circle cx='20' cy='44' r='2' fill='rgba(255,220,150,0.14)'/>",
    "2em 2.8em",
  ),
  stone: tile(
    "width='60' height='44'><g fill='none' stroke='rgba(0,0,0,0.35)' stroke-width='1.6'><path d='M0 14 H22 L26 0 M22 14 L20 30 H0 M20 30 H44 L46 14 H22 M46 14 H60 M44 30 L42 44 M26 0 M46 14 L48 0'/></g><g fill='none' stroke='rgba(255,255,255,0.08)' stroke-width='1'><path d='M1 16 H20 M24 32 H42 M48 16 H59'/></g>",
    "3em 2.2em",
  ),
  ricepaper:
    "repeating-linear-gradient(82deg, rgb(120 100 60 / 0.06) 0 1px, transparent 1px 7px), repeating-linear-gradient(-8deg, rgb(120 100 60 / 0.04) 0 1px, transparent 1px 11px), radial-gradient(ellipse at 50% 40%, transparent 55%, rgb(120 90 40 / 0.25))",
  obsidian:
    "conic-gradient(from 20deg at 30% 30%, rgb(255 255 255 / 0.07), transparent 12%, rgb(255 255 255 / 0.03) 30%, transparent 45%, rgb(255 255 255 / 0.06) 62%, transparent 78%, rgb(255 255 255 / 0.05) 90%, transparent), conic-gradient(from 200deg at 75% 70%, rgb(255 255 255 / 0.05), transparent 15%, rgb(255 255 255 / 0.04) 40%, transparent 60%)",
  stars:
    "radial-gradient(1px 1px at 12% 18%, #fff, transparent), radial-gradient(1px 1px at 63% 9%, #fff, transparent), radial-gradient(1.5px 1.5px at 81% 37%, #fff, transparent), radial-gradient(1px 1px at 33% 52%, rgb(255 255 255 / 0.8), transparent), radial-gradient(1px 1px at 91% 71%, #fff, transparent), radial-gradient(1.5px 1.5px at 22% 83%, rgb(255 255 255 / 0.9), transparent), radial-gradient(1px 1px at 52% 92%, #fff, transparent), radial-gradient(1px 1px at 72% 62%, rgb(255 255 255 / 0.7), transparent)",
  frostbite:
    "radial-gradient(circle at 15% 20%, rgb(255 255 255 / 0.25), transparent 30%), radial-gradient(circle at 85% 85%, rgb(255 255 255 / 0.2), transparent 30%), repeating-linear-gradient(60deg, rgb(255 255 255 / 0.04) 0 1px, transparent 1px 9px), repeating-linear-gradient(-60deg, rgb(255 255 255 / 0.04) 0 1px, transparent 1px 9px)",
  dunes: "repeating-linear-gradient(172deg, rgb(255 255 255 / 0.05) 0 2px, transparent 2px 10px)",
  scales: tile(
    "width='20' height='14'><g fill='none' stroke='rgba(255,200,255,0.22)' stroke-width='1.2'><path d='M0 14 A10 10 0 0 1 20 14'/><path d='M-10 7 A10 10 0 0 1 10 7 M10 7 A10 10 0 0 1 30 7'/></g>",
    "0.9em 0.63em",
  ),
  lead: "linear-gradient(rgb(0 0 0 / 0.25), rgb(0 0 0 / 0.25))",
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
