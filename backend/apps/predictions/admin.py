"""Read-only in the Django admin: coins only move through ``services.post_entry``."""

from django.contrib import admin

from .models import Bet, LedgerEntry, Market, Settlement, Wallet


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Wallet)
class WalletAdmin(ReadOnlyAdmin):
    list_display = ["user", "balance", "entry_count", "created_at"]
    search_fields = ["user__email", "user__display_name"]


@admin.register(LedgerEntry)
class LedgerEntryAdmin(ReadOnlyAdmin):
    list_display = ["created_at", "wallet", "seq", "kind", "amount", "balance_after", "actor"]
    list_filter = ["kind"]
    search_fields = ["wallet__user__email", "idempotency_key"]


@admin.register(Bet)
class BetAdmin(ReadOnlyAdmin):
    list_display = ["placed_at", "user", "market", "outcome", "stake", "odds_accepted", "status"]
    list_filter = ["status"]


@admin.register(Market)
class MarketAdmin(ReadOnlyAdmin):
    list_display = ["title", "category", "status", "closes_at"]
    list_filter = ["status", "category"]


@admin.register(Settlement)
class SettlementAdmin(ReadOnlyAdmin):
    list_display = ["market", "version", "kind", "actor", "created_at"]
