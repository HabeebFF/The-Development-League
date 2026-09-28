from django.contrib import admin

from .models import PlayerMatchResult, TeamMatchResult


@admin.register(TeamMatchResult)
class TeamMatchResultAdmin(admin.ModelAdmin):
    list_display = ["match", "team", "placement", "kills", "total_points"]
    list_filter = ["match__match_day__stage__season"]


@admin.register(PlayerMatchResult)
class PlayerMatchResultAdmin(admin.ModelAdmin):
    list_display = ["match", "display_name", "team", "kills", "knocks"]
    search_fields = ["display_name", "player__game_uid"]
