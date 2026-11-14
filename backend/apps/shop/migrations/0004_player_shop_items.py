from django.db import migrations

# slug, name, kind, rarity, price, (palette, pattern, effect), copies, unlock
ITEMS = [
    # Player frames
    ("pro-circuit", "Pro Circuit", "FRAME", "RARE", 5000, ("cyan", "circuit", "glow"), None, ""),
    ("night-ops", "Night Ops", "FRAME", "RARE", 10000, ("violet", "lines", "none"), None, ""),
    ("blood-moon", "Blood Moon", "FRAME", "EPIC", 50000, ("crimson", "flames", "glow"), None, ""),
    ("booyah-gold", "Booyah Gold", "FRAME", "LEGENDARY", 250000, ("gold", "hex", "shine"), 20, ""),
    (
        "league-legend", "League Legend", "FRAME", "VINTAGE", 1000000,
        ("champion", "flames", "flame"), 10, "",
    ),
    ("apex", "Apex", "FRAME", "DIAMOND", 10000000, ("diamond", "facets", "sparkle"), 1, ""),
    # Card titles (the name is the text on the card)
    ("title-zone-king", "Zone King", "TITLE", "RARE", 5000, ("gold", "none", "none"), None, ""),
    ("title-the-sniper", "The Sniper", "TITLE", "RARE", 5000, ("cyan", "none", "none"), None, ""),
    ("title-nade-god", "Nade God", "TITLE", "RARE", 5000, ("lava", "none", "none"), None, ""),
    ("title-rush-lord", "Rush Lord", "TITLE", "RARE", 5000, ("crimson", "none", "none"), None, ""),
    (
        "title-clutch-king", "Clutch King", "TITLE", "RARE", 5000,
        ("violet", "none", "none"), None, "",
    ),
    (
        "title-shot-caller", "Shot Caller", "TITLE", "RARE", 5000,
        ("emerald", "none", "none"), None, "",
    ),
    # Shirt number and flag
    (
        "number-and-flag", "Number and flag", "NUMBER", "RARE", 10000,
        ("gold", "none", "none"), None, "",
    ),
    # Rating glows
    ("glow-gold", "Gold glow", "GLOW", "EPIC", 25000, ("gold", "none", "glow"), None, ""),
    ("glow-cyan", "Cyan glow", "GLOW", "EPIC", 25000, ("cyan", "none", "glow"), None, ""),
    ("glow-crimson", "Crimson glow", "GLOW", "EPIC", 25000, ("crimson", "none", "glow"), None, ""),
    (
        "glow-diamond", "Diamond glow", "GLOW", "LEGENDARY", 100000,
        ("diamond", "none", "sparkle"), None, "",
    ),
    # Milestone frames: earned, never bought
    ("centurion", "Centurion", "FRAME", "EPIC", 0, ("emerald", "hex", "glow"), None, "kills:100"),
    (
        "booyah-ten", "Booyah x10", "FRAME", "LEGENDARY", 0,
        ("lava", "flames", "glow"), None, "booyahs:10",
    ),
    ("week-star", "Week Star", "FRAME", "EPIC", 0, ("gold", "lines", "shine"), None, "totw:1"),
]


def add(apps, schema_editor):
    CardDesign = apps.get_model("shop", "CardDesign")
    for n, (slug, name, kind, rarity, price, parts, copies, unlock) in enumerate(ITEMS):
        palette, pattern, effect = parts
        CardDesign.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "kind": kind,
                "rarity": rarity,
                "price": price,
                "parts": {"palette": palette, "pattern": pattern, "effect": effect},
                "copies": copies,
                "unlock": unlock,
                "players_only": True,
                "order": 100 + n,
            },
        )


def remove(apps, schema_editor):
    CardDesign = apps.get_model("shop", "CardDesign")
    CardDesign.objects.filter(slug__in=[s[0] for s in ITEMS], owners__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("shop", "0003_player_shop")]

    operations = [migrations.RunPython(add, remove)]
