"""The parts a card design is built from. The site draws each one (see the frontend's
``cardDesigns.ts``), so a design is just a choice of parts: no images to upload.

Keep these keys in step with the frontend; an unknown key falls back to the plain card there.
"""

PALETTES = {
    "carbon": "Carbon black",
    "ocean": "Ocean blue",
    "gold": "Molten gold",
    "cyan": "Neon cyan",
    "crimson": "Crimson",
    "emerald": "Emerald",
    "violet": "Violet",
    "lava": "Lava",
    "holo": "Holo",
    "champion": "Champion gold",
    "vintage": "Vintage sepia",
    "diamond": "Diamond ice",
    # Player shop collection
    "steel": "Brushed steel",
    "gunmetal": "Gunmetal",
    "team": "Team colour",
    "neon": "Neon",
    "sniper": "Sniper green",
    "ember": "Ember",
    "rage": "Rage red",
    "smoke": "Smoke",
    "foil": "Holo foil",
    "zone": "Zone",
    "storm": "Storm",
    "booyah": "Booyah gold",
    "phoenix": "Phoenix",
    "void": "Void",
    # Player shop art series
    "noir": "Liberty Noir",
    "vice": "Neon Vice",
    "wanted": "Wanted paper",
    "comic": "Comic",
    "anime": "Anime",
    "glitch": "Glitch",
    "vapor": "Vaporwave",
    "graffiti": "Graffiti",
    "dossier": "Dossier",
    "prism": "Prism",
    "blueprint": "Blueprint",
    "arcade": "Arcade",
    "afro": "Afrofuturism",
    "lagos": "Lagos Nights",
    "magma": "Magma",
    "frost": "Frost",
    "chaser": "Storm Chaser",
    "royal": "Royal velvet",
    "ink": "Ink",
    "steam": "Steampunk",
    "station": "Space Station",
    "toxic": "Toxic",
    "mirage": "Mirage",
    "ruins": "Ruins",
    "racer": "Racer",
    "classic": "Trading card",
    "glass": "Stained glass",
    "assassin": "Shadow",
    "dragon": "Galaxy Dragon",
    "platinum": "Platinum",
}

PATTERNS = {
    "none": "None",
    "carbon": "Carbon weave",
    "lines": "Speed lines",
    "hex": "Hexagons",
    "circuit": "Circuit",
    "flames": "Flames",
    "paper": "Aged paper",
    "facets": "Diamond facets",
    "brushed": "Brushed metal",
    "scope": "Scope marks",
    # Player shop art series
    "grain": "Film grain",
    "halftone": "Halftone",
    "scanlines": "Scanlines",
    "bpgrid": "Blueprint grid",
    "brick": "Brick",
    "pixel": "Pixel grid",
    "velvet": "Velvet damask",
    "stone": "Stone blocks",
    "ricepaper": "Rice paper",
    "obsidian": "Obsidian",
    "stars": "Stars",
    "frostbite": "Frost",
    "dunes": "Dunes",
    "scales": "Dragon scales",
    "lead": "Lead glass",
}

EFFECTS = {
    "none": "None",
    "glow": "Moving glow",
    "shine": "Tilting shine",
    "flame": "Flame frame",
    "sparkle": "Sparkle",
    "metal": "Metal shine",
    "neon": "Neon edges",
    "scope": "Scope and scan line",
    "embers": "Rising embers",
    "lightning": "Lightning",
    "smoke": "Smoke and blast",
    "foil": "Holo foil (tilt)",
    "zone": "Closing zone",
    "storm": "Storm",
    "goldrain": "Gold rain",
    "phoenix": "Phoenix wings",
    "void": "Void vortex",
    # Player shop art series
    "noir": "Crime-city panels",
    "vice": "80s sunset",
    "wanted": "Wanted poster",
    "comic": "Comic splash",
    "anime": "Anime aura",
    "glitch": "Glitch",
    "vapor": "Vaporwave",
    "graffiti": "Graffiti",
    "dossier": "Dossier",
    "prism": "Prism foil (tilt)",
    "blueprint": "Blueprint",
    "arcade": "Arcade",
    "afro": "Afrofuturism",
    "lagos": "Lagos skyline",
    "lava": "Magma veins",
    "frost": "Ice and fog",
    "chaser": "Supercell",
    "royal": "Royal crest",
    "ink": "Ink brush",
    "steam": "Gears",
    "station": "Space HUD",
    "toxic": "Toxic zone",
    "mirage": "Mirage",
    "ruins": "Ruins",
    "racer": "Speedometer",
    "classic": "Trading card",
    "glass": "Stained glass",
    "assassin": "Shadow assassin",
    "dragon": "Galaxy dragon",
    "platinum": "Platinum",
}

PARTS = {"palette": PALETTES, "pattern": PATTERNS, "effect": EFFECTS}


def clean_parts(parts: dict) -> dict:
    """The parts with unknown keys refused; raises ``ValueError`` with a message to show."""
    if not isinstance(parts, dict):
        raise ValueError("Pick a palette, a pattern and an effect.")
    out = {}
    for name, options in PARTS.items():
        value = parts.get(name, "none" if name != "palette" else None)
        if value not in options:
            raise ValueError(f"Unknown {name}: {value!r}. Use one of: {', '.join(options)}.")
        out[name] = value
    return out


def catalogue() -> dict:
    """Every part with its label, for the staff editor."""
    return {
        name: [{"key": k, "label": v} for k, v in options.items()]
        for name, options in PARTS.items()
    }
