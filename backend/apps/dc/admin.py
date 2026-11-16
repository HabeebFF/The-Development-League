from django.contrib import admin

from .models import DcSettings, MatchReward, Perk, PerkPurchase, PotEntry, Spotlight, TeamPot


@admin.register(DcSettings)
class DcSettingsAdmin(admin.ModelAdmin):
    list_display = ["rewards_enabled", "per_kill", "booyah", "mvp", "played", "start_date"]


@admin.register(MatchReward)
class MatchRewardAdmin(admin.ModelAdmin):
    list_display = ["match", "player", "kills", "booyah", "mvp", "amount", "paid", "shortfall"]
    raw_id_fields = ["match", "player", "team", "paid_to"]
    list_filter = ["booyah", "mvp"]


@admin.register(Spotlight)
class SpotlightAdmin(admin.ModelAdmin):
    list_display = ["month", "player", "earned", "from_matches", "hidden"]
    raw_id_fields = ["player"]


admin.site.register(Perk)
admin.site.register(TeamPot)
admin.site.register(PotEntry)


@admin.register(PerkPurchase)
class PerkPurchaseAdmin(admin.ModelAdmin):
    list_display = ["perk", "user", "team", "player", "status", "price_paid", "created_at"]
    list_filter = ["perk", "status"]
    raw_id_fields = ["user", "player", "team", "reviewed_by"]
