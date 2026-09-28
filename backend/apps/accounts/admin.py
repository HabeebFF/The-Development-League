from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Feature, Invite, Membership, Plan, PlayerClaim, StaffProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "display_name", "is_staff", "is_superuser", "is_active"]
    search_fields = ["email", "display_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("display_name", "preferred_language")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "created_at"]


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ["code", "description"]


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["code", "name"]
    filter_horizontal = ["features"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "team", "role", "is_active"]
    list_filter = ["role", "is_active", "team"]
    search_fields = ["user__email", "team__name"]


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ["email", "team", "role", "expires_at", "accepted_at", "revoked_at"]
    search_fields = ["email", "team__name"]
    readonly_fields = ["token"]


@admin.register(PlayerClaim)
class PlayerClaimAdmin(admin.ModelAdmin):
    list_display = ["user", "game_uid", "status", "reviewed_by", "created_at"]
    list_filter = ["status"]
