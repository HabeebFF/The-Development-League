from django.contrib import admin

from .models import CoachQuestion, KnowledgeEntry, WeaponName


@admin.register(KnowledgeEntry)
class KnowledgeEntryAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "map", "updated_at"]
    list_filter = ["kind", "map"]
    search_fields = ["title", "body"]


@admin.register(WeaponName)
class WeaponNameAdmin(admin.ModelAdmin):
    list_display = ["weapon_id", "name", "weapon_class"]


@admin.register(CoachQuestion)
class CoachQuestionAdmin(admin.ModelAdmin):
    list_display = ["created_at", "team", "question", "writer"]
    list_filter = ["team", "writer"]
    search_fields = ["question"]
    readonly_fields = ["created_at", "team", "asked_by", "question", "answer", "writer"]
