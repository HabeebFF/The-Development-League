from django.contrib import admin

from .models import Group, Match, MatchDay, Player, ScoringRule, Season, Stage, Team, TeamAlias


@admin.register(ScoringRule)
class ScoringRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "points_per_kill", "default_points"]


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ["name", "starts_on", "ends_on", "is_active", "scoring_rule"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ["name", "season", "order", "kind"]
    list_filter = ["season"]


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name", "stage"]
    filter_horizontal = ["teams"]


@admin.register(MatchDay)
class MatchDayAdmin(admin.ModelAdmin):
    list_display = ["__str__", "stage", "group", "number", "date"]
    list_filter = ["stage__season", "stage"]


class TeamAliasInline(admin.TabularInline):
    model = TeamAlias
    extra = 0


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["name", "tag", "is_league_member"]
    search_fields = ["name", "tag", "aliases__in_game_name"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [TeamAliasInline]


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ["display_name", "game_uid", "current_team"]
    search_fields = ["display_name", "search_name", "game_uid"]


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ["__str__", "game_match_id", "map", "status", "started_at"]
    list_filter = ["status", "match_day__stage__season", "map"]
    search_fields = ["game_match_id", "room_name"]
