from django.db import migrations

# The Player shop art series (Habeeb 2026-11-24): 30 designs from 5,000 to 10,000,000 DC, and
# four earned-only TDL Cup designs (winners, 2nd, 3rd, MVP) given on Confirm & pay.
# Keep in step with the frontend's lib/playerDesigns.ts (ART_SERIES, CUP_DESIGNS).
# slug, name, rarity, price, (palette, pattern, effect), copies, unlock
ITEMS = [
    ("blueprint", "Blueprint", "COMMON", 5_000, ("blueprint", "bpgrid", "blueprint"), None, ""),
    ("trading-card-classic", "Trading Card Classic", "COMMON", 8_000, ("classic", "grain", "classic"), None, ""),
    ("wanted-poster", "Wanted Poster", "COMMON", 10_000, ("wanted", "paper", "wanted"), None, ""),
    ("military-dossier", "Military Dossier", "COMMON", 12_000, ("dossier", "paper", "dossier"), None, ""),
    ("graffiti-wall", "Graffiti Wall", "COMMON", 15_000, ("graffiti", "brick", "graffiti"), None, ""),
    ("vaporwave", "Vaporwave", "COMMON", 18_000, ("vapor", "none", "vapor"), None, ""),
    ("jungle-ruins", "Jungle Ruins", "COMMON", 22_000, ("ruins", "stone", "ruins"), None, ""),
    ("stained-glass", "Stained Glass", "COMMON", 25_000, ("glass", "lead", "glass"), None, ""),
    ("comic-splash", "Comic Splash", "RARE", 50_000, ("comic", "halftone", "comic"), None, ""),
    ("retro-arcade", "Retro Arcade", "RARE", 65_000, ("arcade", "pixel", "arcade"), None, ""),
    ("neon-vice", "Neon Vice", "RARE", 80_000, ("vice", "none", "vice"), None, ""),
    ("lagos-nights", "Lagos Nights", "RARE", 90_000, ("lagos", "none", "lagos"), None, ""),
    ("desert-mirage", "Desert Mirage", "RARE", 100_000, ("mirage", "dunes", "mirage"), None, ""),
    ("street-racer", "Street Racer", "RARE", 120_000, ("racer", "carbon", "racer"), None, ""),
    ("toxic-zone", "Toxic Zone", "RARE", 135_000, ("toxic", "none", "toxic"), None, ""),
    ("samurai-ink", "Samurai Ink", "RARE", 150_000, ("ink", "ricepaper", "ink"), None, ""),
    ("liberty-noir", "Liberty Noir", "EPIC", 250_000, ("noir", "grain", "noir"), None, ""),
    ("steampunk", "Steampunk", "EPIC", 300_000, ("steam", "brushed", "steam"), None, ""),
    ("frostbite", "Frostbite", "EPIC", 375_000, ("frost", "frostbite", "frost"), None, ""),
    ("cyberpunk-glitch", "Cyberpunk Glitch", "EPIC", 450_000, ("glitch", "scanlines", "glitch"), None, ""),
    ("storm-chaser", "Storm Chaser", "EPIC", 550_000, ("chaser", "none", "chaser"), None, ""),
    ("holographic-prism", "Holographic Prism", "EPIC", 650_000, ("prism", "none", "prism"), None, ""),
    ("anime-ultimate", "Anime Ultimate", "EPIC", 750_000, ("anime", "none", "anime"), None, ""),
    ("lava-core", "Lava Core", "LEGENDARY", 1_000_000, ("magma", "obsidian", "lava"), 50, ""),
    ("space-station", "Space Station", "LEGENDARY", 1_500_000, ("station", "none", "station"), 40, ""),
    ("afrofuturism", "Afrofuturism", "LEGENDARY", 2_000_000, ("afro", "none", "afro"), 30, ""),
    ("royal-gold", "Royal Gold", "LEGENDARY", 3_000_000, ("royal", "velvet", "royal"), 20, ""),
    ("shadow-assassin", "Shadow Assassin", "MYTHIC", 5_000_000, ("assassin", "none", "assassin"), 10, ""),
    ("galaxy-dragon", "Galaxy Dragon", "MYTHIC", 7_500_000, ("dragon", "scales", "dragon"), 5, ""),
    ("champion-platinum", "Champion Platinum", "MYTHIC", 10_000_000, ("platinum", "brushed", "platinum"), 1, ""),
    ("cup-champions", "Cup Champions", "MYTHIC", 0, ("cupgold", "hex", "cupwin"), None, "cupwin:1"),
    ("cup-runners-up", "Cup Runners-up", "LEGENDARY", 0, ("cupsilver", "hex", "cupsecond"), None, "cupsecond:1"),
    ("cup-third-place", "Cup Third Place", "LEGENDARY", 0, ("cupbronze", "hex", "cupthird"), None, "cupthird:1"),
    ("cup-mvp", "Cup MVP", "MYTHIC", 0, ("cupmvp", "hex", "cupmvp"), None, "cupmvp:1"),
]


def add(apps, schema_editor):
    CardDesign = apps.get_model("shop", "CardDesign")
    for n, (slug, name, rarity, price, parts, copies, unlock) in enumerate(ITEMS):
        palette, pattern, effect = parts
        CardDesign.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "kind": "FRAME",
                "rarity": rarity,
                "price": price,
                "parts": {"palette": palette, "pattern": pattern, "effect": effect},
                "copies": copies,
                "unlock": unlock,
                "players_only": True,
                "order": 200 + n,
            },
        )


def remove(apps, schema_editor):
    CardDesign = apps.get_model("shop", "CardDesign")
    CardDesign.objects.filter(slug__in=[s[0] for s in ITEMS], owners__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("shop", "0004_player_shop_items")]

    operations = [migrations.RunPython(add, remove)]
