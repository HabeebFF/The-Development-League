// The Player shop collection: card designs only league players can buy, with DC.
// Keep slugs and parts in step with backend apps/shop/migrations (player shop items).

import type { CardDesign } from "./cardDesigns";
import type { PlayerCard as Card } from "./cards";

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

// The art series: 30 more designs in every tier, from 5,000 DC to 10M DC.
// Parts are [palette, pattern, effect]; each effect is drawn in components/league/CardArt.tsx.
export const ART_SERIES: CollectionDesign[] = [
  // Common: still art, 5k to 25k.
  d(16, "blueprint", "Blueprint", "COMMON", 5_000, ["blueprint", "bpgrid", "blueprint"], "White line drawings on engineering blue."),
  d(17, "trading-card-classic", "Trading Card Classic", "COMMON", 8_000, ["classic", "grain", "classic"], "A 90s cardboard card with a foil border."),
  d(18, "wanted-poster", "Wanted Poster", "COMMON", 10_000, ["wanted", "paper", "wanted"], "Worn paper. Your bounty is your rating."),
  d(19, "military-dossier", "Military Dossier", "COMMON", 12_000, ["dossier", "paper", "dossier"], "Camo frame, classified stamp, redacted lines."),
  d(20, "graffiti-wall", "Graffiti Wall", "COMMON", 15_000, ["graffiti", "brick", "graffiti"], "Spray tags and drips on a brick wall."),
  d(21, "vaporwave", "Vaporwave", "COMMON", 18_000, ["vapor", "none", "vapor"], "Pastel sky, marble bust and a grid floor."),
  d(22, "jungle-ruins", "Jungle Ruins", "COMMON", 22_000, ["ruins", "stone", "ruins"], "Carved stone, hanging vines and moss."),
  d(23, "stained-glass", "Stained Glass", "COMMON", 25_000, ["glass", "lead", "glass"], "Jewel-coloured panes in lead lines."),
  // Rare: animated, 50k to 150k.
  d(24, "comic-splash", "Comic Splash", "RARE", 50_000, ["comic", "halftone", "comic"], "Halftone dots, a POW burst, stats in a speech bubble."),
  d(25, "retro-arcade", "Retro Arcade", "RARE", 65_000, ["arcade", "pixel", "arcade"], "8-bit pixel art, a high score and CRT glow."),
  d(26, "neon-vice", "Neon Vice", "RARE", 80_000, ["vice", "none", "vice"], "An 80s sunset, pink and teal neon, palms."),
  d(27, "lagos-nights", "Lagos Nights", "RARE", 90_000, ["lagos", "none", "lagos"], "The skyline at night, danfo yellow and neon."),
  d(28, "desert-mirage", "Desert Mirage", "RARE", 100_000, ["mirage", "dunes", "mirage"], "Heat shimmer over the dunes. A Kalahari nod.", { ff: true }),
  d(29, "street-racer", "Street Racer", "RARE", 120_000, ["racer", "carbon", "racer"], "Carbon fibre, and a speedometer for your rating."),
  d(30, "toxic-zone", "Toxic Zone", "RARE", 135_000, ["toxic", "none", "toxic"], "Hazard tape and a glowing gas wall closing in.", { ff: true }),
  d(31, "samurai-ink", "Samurai Ink", "RARE", 150_000, ["ink", "ricepaper", "ink"], "Sumi-e brush strokes and a red seal."),
  // Epic: full motion, 250k to 750k.
  d(32, "liberty-noir", "Liberty Noir", "EPIC", 250_000, ["noir", "grain", "noir"], "Painted crime-city panels, thick black lines, sepia smog."),
  d(33, "steampunk", "Steampunk", "EPIC", 300_000, ["steam", "brushed", "steam"], "Brass gears turning, copper rivets, a live gauge."),
  d(34, "frostbite", "Frostbite", "EPIC", 375_000, ["frost", "frostbite", "frost"], "An ice-crystal frame and drifting breath fog."),
  d(35, "cyberpunk-glitch", "Cyberpunk Glitch", "EPIC", 450_000, ["glitch", "scanlines", "glitch"], "RGB split, scanlines and flicker."),
  d(36, "storm-chaser", "Storm Chaser", "EPIC", 550_000, ["chaser", "none", "chaser"], "Lightning strikes across a spinning supercell."),
  d(37, "holographic-prism", "Holographic Prism", "EPIC", 650_000, ["prism", "none", "prism"], "Rainbow prism foil that shifts as you tilt."),
  d(38, "anime-ultimate", "Anime Ultimate", "EPIC", 750_000, ["anime", "none", "anime"], "Speed lines, a power-up aura, brush lettering."),
  // Legendary: animated scenes, glowing frame, entrance, limited copies.
  d(39, "lava-core", "Lava Core", "LEGENDARY", 1_000_000, ["magma", "obsidian", "lava"], "Cracked obsidian with glowing magma veins.", { copies: 50 }),
  d(40, "space-station", "Space Station", "LEGENDARY", 1_500_000, ["station", "none", "station"], "Starfield, planet glow and HUD readouts.", { copies: 40 }),
  d(41, "afrofuturism", "Afrofuturism", "LEGENDARY", 2_000_000, ["afro", "none", "afro"], "Cosmic purple, gold orbits, kente-inspired weave.", { copies: 30 }),
  d(42, "royal-gold", "Royal Gold", "LEGENDARY", 3_000_000, ["royal", "velvet", "royal"], "Velvet, gold filigree and a crown crest.", { copies: 20 }),
  // Mythic: numbered, animated, name aura across the site.
  d(43, "shadow-assassin", "Shadow Assassin", "MYTHIC", 5_000_000, ["assassin", "none", "assassin"], "Smoke, a hooded silhouette, red eyes. Only 10 ever.", { copies: 10 }),
  d(44, "galaxy-dragon", "Galaxy Dragon", "MYTHIC", 7_500_000, ["dragon", "scales", "dragon"], "A nebula dragon coiled round your card. Only 5 ever.", { copies: 5 }),
  d(45, "champion-platinum", "Champion Platinum", "MYTHIC", 10_000_000, ["platinum", "brushed", "platinum"], "Brushed platinum, engraved laurel. One of one.", { copies: 1 }),
];

export const TIERS: { rarity: CardDesign["rarity"]; label: string; range: string; perks: string }[] = [
  { rarity: "COMMON", label: "Common", range: "5k to 25k DC", perks: "Clean metals and team colours" },
  { rarity: "RARE", label: "Rare", range: "50k to 150k DC", perks: "Animated shine, carbon fibre, neon edges" },
  { rarity: "EPIC", label: "Epic", range: "250k to 750k DC", perks: "Moving particles and holo foil" },
  { rarity: "LEGENDARY", label: "Legendary", range: "1M to 3M DC", perks: "Animated scenes, glowing frame, entrance animation" },
  { rarity: "MYTHIC", label: "Mythic", range: "5M to 10M DC", perks: "Numbered copies, unique animation, name aura across the site" },
];

/** What each tier gets in the art series. */
export const ART_TIERS: typeof TIERS = [
  { rarity: "COMMON", label: "Common", range: "5k to 25k DC", perks: "Still art, every style" },
  { rarity: "RARE", label: "Rare", range: "50k to 150k DC", perks: "Animated art" },
  { rarity: "EPIC", label: "Epic", range: "250k to 750k DC", perks: "Full motion scenes" },
  { rarity: "LEGENDARY", label: "Legendary", range: "1M to 3M DC", perks: "Glowing frame, entrance animation, limited copies" },
  { rarity: "MYTHIC", label: "Mythic", range: "5M to 10M DC", perks: "Numbered, animated, name aura across the site" },
];

/** "1M", "250k", "5,000". */
export function shortDc(n: number): string {
  if (n >= 1_000_000) return `${n / 1_000_000}M`;
  if (n >= 50_000) return `${n / 1_000}k`;
  return n.toLocaleString("en-GB");
}

// A stand-in player so every design can be seen on a real card layout.
export const SAMPLE_CARD: Card = {
  player_id: 0,
  name: "Your name",
  photo: null,
  team: { id: 0, name: "Your team", tag: "TDL", slug: "", logo: null, primary_color: "#c81e3c" },
  week: "2026-11-14",
  role: "RUSHER",
  role_label: "Rusher",
  role_suggested: false,
  suggested_role: "RUSHER",
  overall: 88,
  overall_change: 3,
  tier: "gold",
  totw: [],
  stats: [
    ["ENT", 91],
    ["CQC", 89],
    ["FIN", 86],
    ["AIM", 84],
    ["TRD", 80],
    ["SUR", 77],
  ].map(([key, rating]) => ({ key: key as string, label: key as string, rating: rating as number, change: null, stale: false, value: null, detail: "" })),
  matches: 20,
  week_matches: 6,
  stale: false,
};

