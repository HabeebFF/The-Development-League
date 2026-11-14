// The Player shop collection: card designs only league players can buy, with DC.
// Keep slugs and parts in step with backend apps/shop/migrations (player shop items).

import type { CardDesign } from "./cardDesigns";

export type CollectionDesign = CardDesign & {
  price: number;
  /** One line on what you get. */
  blurb: string;
  /** Free Fire themed. */
  ff?: boolean;
};

const d = (
  id: number,
  slug: string,
  name: string,
  rarity: CardDesign["rarity"],
  price: number,
  [palette, pattern, effect]: [string, string, string],
  blurb: string,
  extra: { copies?: number; ff?: boolean } = {},
): CollectionDesign => ({
  id,
  slug,
  name,
  rarity,
  price,
  parts: { palette, pattern, effect },
  copies: extra.copies ?? null,
  copy_number: extra.copies ? Math.max(1, Math.round(extra.copies * 0.3)) : null,
  blurb,
  ff: extra.ff,
});

export const COLLECTION: CollectionDesign[] = [
  // Common: clean metals and team colours.
  d(1, "brushed-steel", "Brushed Steel", "COMMON", 5_000, ["steel", "brushed", "metal"], "Polished steel with a bright edge."),
  d(2, "gunmetal-gold", "Gunmetal Gold", "COMMON", 12_000, ["gunmetal", "brushed", "metal"], "Dark gunmetal, molten gold trim."),
  d(3, "team-colours", "Team Colours", "COMMON", 25_000, ["team", "lines", "metal"], "Painted in your own team's colour."),
  // Rare: animated shine, carbon fibre, neon edges.
  d(4, "carbon-strike", "Carbon Strike", "RARE", 50_000, ["carbon", "carbon", "shine"], "Carbon fibre with a moving shine."),
  d(5, "neon-edge", "Neon Edge", "RARE", 100_000, ["neon", "circuit", "neon"], "Neon edges that pulse and run."),
  d(6, "sniper-elite", "Sniper Elite", "RARE", 150_000, ["sniper", "scope", "scope"], "A scope that locks on, with a scan line.", { ff: true }),
  // Epic: particles and foil.
  d(7, "ember-storm", "Ember Storm", "EPIC", 250_000, ["ember", "none", "embers"], "Embers rising off a burning base."),
  d(8, "rusher-rage", "Rusher Rage", "EPIC", 400_000, ["rage", "lines", "lightning"], "Red lightning cracks across the card.", { ff: true }),
  d(9, "grenade-master", "Grenade Master", "EPIC", 550_000, ["smoke", "hex", "smoke"], "Smoke, sparks and a blast ring.", { ff: true }),
  d(10, "holo-foil", "Holo Foil", "EPIC", 750_000, ["foil", "none", "foil"], "Rainbow foil that shifts as you tilt or scroll."),
  // Legendary: full animated scenes, glowing frame, entrance animation.
  d(11, "zone-king", "Zone King", "LEGENDARY", 1_000_000, ["zone", "none", "zone"], "The safe zone closing in, the edges burning.", { copies: 50, ff: true }),
  d(12, "bermuda-storm", "Bermuda Storm", "LEGENDARY", 2_000_000, ["storm", "none", "storm"], "Storm clouds, rain and lightning.", { copies: 30 }),
  d(13, "booyah-gold", "Booyah Gold", "LEGENDARY", 3_000_000, ["booyah", "hex", "goldrain"], "Gold raining down on a Booyah.", { copies: 20, ff: true }),
  // Mythic: numbered, one of a kind, and a name aura across the site.
  d(14, "phoenix-rising", "Phoenix Rising", "MYTHIC", 5_000_000, ["phoenix", "none", "phoenix"], "Burning wings behind you. Only 10 ever.", { copies: 10 }),
  d(15, "void-monarch", "Void Monarch", "MYTHIC", 10_000_000, ["void", "none", "void"], "A purple vortex and stars. Only 3 ever.", { copies: 3 }),
];

export const TIERS: { rarity: CardDesign["rarity"]; label: string; range: string; perks: string }[] = [
  { rarity: "COMMON", label: "Common", range: "5k to 25k DC", perks: "Clean metals and team colours" },
  { rarity: "RARE", label: "Rare", range: "50k to 150k DC", perks: "Animated shine, carbon fibre, neon edges" },
  { rarity: "EPIC", label: "Epic", range: "250k to 750k DC", perks: "Moving particles and holo foil" },
  { rarity: "LEGENDARY", label: "Legendary", range: "1M to 3M DC", perks: "Animated scenes, glowing frame, entrance animation" },
  { rarity: "MYTHIC", label: "Mythic", range: "5M to 10M DC", perks: "Numbered copies, unique animation, name aura across the site" },
];

/** "1M", "250k", "5,000". */
export function shortDc(n: number): string {
  if (n >= 1_000_000) return `${n / 1_000_000}M`;
  if (n >= 50_000) return `${n / 1_000}k`;
  return n.toLocaleString("en-GB");
}
