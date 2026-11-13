from django.db import migrations

STARTING = [
    # slug, name, rarity, price, palette, pattern, effect, copies
    ("carbon-black", "Carbon Black", "COMMON", 1500, "carbon", "carbon", "none", None),
    ("ocean-blue", "Ocean Blue", "COMMON", 1500, "ocean", "lines", "none", None),
    ("molten-gold", "Molten Gold", "RARE", 5000, "gold", "hex", "none", None),
    ("neon-cyan", "Neon Cyan", "RARE", 5000, "cyan", "circuit", "none", None),
    ("crimson", "Crimson", "RARE", 5000, "crimson", "lines", "none", None),
    ("lava-flow", "Lava Flow", "EPIC", 15000, "lava", "flames", "glow", None),
    ("holo-shine", "Holo Shine", "EPIC", 15000, "holo", "hex", "shine", None),
    ("champion", "Champion", "LEGENDARY", 40000, "champion", "flames", "flame", 20),
    ("vintage", "Vintage", "VINTAGE", 100000, "vintage", "paper", "none", 10),
    ("diamond", "Diamond", "DIAMOND", 1000000, "diamond", "facets", "sparkle", 1),
]


def add(apps, schema_editor):
    CardDesign = apps.get_model("shop", "CardDesign")
    for n, (slug, name, rarity, price, palette, pattern, effect, copies) in enumerate(STARTING):
        CardDesign.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "rarity": rarity,
                "price": price,
                "parts": {"palette": palette, "pattern": pattern, "effect": effect},
                "copies": copies,
                "order": n,
            },
        )


def remove(apps, schema_editor):
    CardDesign = apps.get_model("shop", "CardDesign")
    CardDesign.objects.filter(slug__in=[s[0] for s in STARTING], owners__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("shop", "0001_card_shop")]

    operations = [migrations.RunPython(add, remove)]
