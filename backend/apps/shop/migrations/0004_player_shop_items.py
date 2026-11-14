from django.db import migrations

# The Player shop: designs only league players can buy, with DC (Habeeb 2026-11-14: 5,000 to
# 10,000,000 DC). Keep in step with the frontend's lib/playerDesigns.ts.
# slug, name, kind, rarity, price, (palette, pattern, effect), copies, unlock
ITEMS = [
    # The collection: card designs in five tiers.
    ("brushed-steel", "Brushed Steel", "FRAME", "COMMON", 5_000, ("steel", "brushed", "metal"), None, ""),
    ("gunmetal-gold", "Gunmetal Gold", "FRAME", "COMMON", 12_000, ("gunmetal", "brushed", "metal"), None, ""),
    ("team-colours", "Team Colours", "FRAME", "COMMON", 25_000, ("team", "lines", "metal"), None, ""),
    ("carbon-strike", "Carbon Strike", "FRAME", "RARE", 50_000, ("carbon", "carbon", "shine"), None, ""),
    ("neon-edge", "Neon Edge", "FRAME", "RARE", 100_000, ("neon", "circuit", "neon"), None, ""),
    ("sniper-elite", "Sniper Elite", "FRAME", "RARE", 150_000, ("sniper", "scope", "scope"), None, ""),
    ("ember-storm", "Ember Storm", "FRAME", "EPIC", 250_000, ("ember", "none", "embers"), None, ""),
    ("rusher-rage", "Rusher Rage", "FRAME", "EPIC", 400_000, ("rage", "lines", "lightning"), None, ""),
    ("grenade-master", "Grenade Master", "FRAME", "EPIC", 550_000, ("smoke", "hex", "smoke"), None, ""),
    ("holo-foil", "Holo Foil", "FRAME", "EPIC", 750_000, ("foil", "none", "foil"), None, ""),
    ("zone-king", "Zone King", "FRAME", "LEGENDARY", 1_000_000, ("zone", "none", "zone"), 50, ""),
    ("bermuda-storm", "Bermuda Storm", "FRAME", "LEGENDARY", 2_000_000, ("storm", "none", "storm"), 30, ""),
    ("booyah-gold", "Booyah Gold", "FRAME", "LEGENDARY", 3_000_000, ("booyah", "hex", "goldrain"), 20, ""),
    ("phoenix-rising", "Phoenix Rising", "FRAME", "MYTHIC", 5_000_000, ("phoenix", "none", "phoenix"), 10, ""),
    ("void-monarch", "Void Monarch", "FRAME", "MYTHIC", 10_000_000, ("void", "none", "void"), 3, ""),
    # Card titles (the name is the text on the card).
    ("title-zone-king", "Zone King", "TITLE", "RARE", 5_000, ("gold", "none", "none"), None, ""),
    ("title-the-sniper", "The Sniper", "TITLE", "RARE", 5_000, ("cyan", "none", "none"), None, ""),
    ("title-nade-god", "Nade God", "TITLE", "RARE", 5_000, ("lava", "none", "none"), None, ""),
    ("title-rush-lord", "Rush Lord", "TITLE", "RARE", 5_000, ("crimson", "none", "none"), None, ""),
    ("title-clutch-king", "Clutch King", "TITLE", "RARE", 5_000, ("violet", "none", "none"), None, ""),
    ("title-shot-caller", "Shot Caller", "TITLE", "RARE", 5_000, ("emerald", "none", "none"), None, ""),
    # Shirt number and flag.
    ("number-and-flag", "Number and flag", "NUMBER", "RARE", 10_000, ("gold", "none", "none"), None, ""),
    # Rating glows.
    ("glow-gold", "Gold glow", "GLOW", "EPIC", 25_000, ("gold", "none", "glow"), None, ""),
    ("glow-cyan", "Cyan glow", "GLOW", "EPIC", 25_000, ("cyan", "none", "glow"), None, ""),
    ("glow-crimson", "Crimson glow", "GLOW", "EPIC", 25_000, ("crimson", "none", "glow"), None, ""),
    ("glow-diamond", "Diamond glow", "GLOW", "LEGENDARY", 100_000, ("diamond", "none", "sparkle"), None, ""),
    # Milestone frames: earned by playing, never bought.
    ("centurion", "Centurion", "FRAME", "EPIC", 0, ("emerald", "hex", "glow"), None, "kills:100"),
    ("booyah-ten", "Booyah x10", "FRAME", "LEGENDARY", 0, ("lava", "flames", "embers"), None, "booyahs:10"),
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
