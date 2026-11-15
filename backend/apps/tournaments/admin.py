from django.contrib import admin

from .models import PrizePayout, Tournament


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ["name", "starts_on", "ends_on", "confirmed_at"]


@admin.register(PrizePayout)
class PrizePayoutAdmin(admin.ModelAdmin):
    list_display = ["tournament", "label", "player", "amount", "paid_at"]
    list_filter = ["tournament"]
