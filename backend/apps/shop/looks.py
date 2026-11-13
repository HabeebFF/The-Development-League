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
}

PATTERNS = {
    "none": "None",
    "carbon": "Carbon weave",
    "lines": "Speed lines",
    "hex": "Hexagons",
    "circuit": "Circuit",
    "flames": "Flames",
}

EFFECTS = {
    "none": "None",
    "glow": "Moving glow",
    "shine": "Tilting shine",
    "flame": "Flame frame",
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
