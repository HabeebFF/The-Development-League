from django.contrib import admin

from .models import Map


@admin.register(Map)
class MapAdmin(admin.ModelAdmin):
    list_display = ["name", "game_map_id", "is_active"]
    prepopulated_fields = {"slug": ("name",)}
