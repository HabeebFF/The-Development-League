from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("admin/shop/designs", views.DesignAdminViewSet, basename="admin-shop-design")

urlpatterns = [
    *router.urls,
    path("admin/shop/sales", views.SalesAdminView.as_view(), name="admin-shop-sales"),
    path(
        "admin/shop/sales/<uuid:pk>/refund",
        views.RefundAdminView.as_view(),
        name="admin-shop-refund",
    ),
    path("admin/shop/gift", views.GiftAdminView.as_view(), name="admin-shop-gift"),
    path("admin/shop/unequip", views.UnequipAdminView.as_view(), name="admin-shop-unequip"),
    path("shop/designs", views.DesignListView.as_view(), name="shop-designs"),
    path("shop/designs/<int:pk>/buy", views.BuyView.as_view(), name="shop-buy"),
    path("shop/equip", views.EquipView.as_view(), name="shop-equip"),
    path("shop/me", views.MeView.as_view(), name="shop-me"),
]
