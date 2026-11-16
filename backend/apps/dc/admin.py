from django.contrib import admin

from .models import DcSettings, MatchReward


@admin.register(DcSettings)
class DcSettingsAdmin(admin.ModelAdmin):
    list_display = ["rewards_enabled", "per_kill", "booyah", "mvp", "played", "start_date"]


@admin.register(MatchReward)
class MatchRewardAdmin(admin.ModelAdmin):
    list_display = ["match", "player", "kills", "booyah", "mvp", "amount", "paid", "shortfall"]
    raw_id_fields = ["match", "player", "team", "paid_to"]
    list_filter = ["booyah", "mvp"]
