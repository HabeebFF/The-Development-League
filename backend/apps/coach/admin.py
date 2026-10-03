from django.contrib import admin

from .models import KnowledgeEntry, WeaponName


@admin.register(KnowledgeEntry)
class KnowledgeEntryAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "map", "updated_at"]
    list_filter = ["kind", "map"]
    search_fields = ["title", "body"]


@admin.register(WeaponName)
class WeaponNameAdmin(admin.ModelAdmin):
    list_display = ["weapon_id", "name", "weapon_class"]
