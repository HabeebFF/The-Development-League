from django.contrib import admin

from .models import CardDesign, Equipped, OwnedDesign


@admin.register(CardDesign)
class CardDesignAdmin(admin.ModelAdmin):
    list_display = ["name", "rarity", "price", "copies", "on_sale", "order"]


@admin.register(OwnedDesign)
class OwnedDesignAdmin(admin.ModelAdmin):
    """Read only: purchases and refunds move coins, so they go through the staff pages."""

    list_display = ["user", "design", "copy_number", "price_paid", "created_at", "refunded_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Equipped)
class EquippedAdmin(admin.ModelAdmin):
    list_display = ["user", "design", "favourite_team"]
