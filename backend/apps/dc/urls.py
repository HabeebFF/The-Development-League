from django.urls import path

from . import views

urlpatterns = [
    path("dc/me", views.MeView.as_view(), name="dc-me"),
    path("dc/waiting", views.WaitingView.as_view(), name="dc-waiting"),
    path("dc/perks", views.PerksView.as_view(), name="dc-perks"),
    path("dc/perks/buy", views.BuyPerkView.as_view(), name="dc-perks-buy"),
    path("dc/perks/live", views.LivePerksView.as_view(), name="dc-perks-live"),
    path("dc/pot", views.PotView.as_view(), name="dc-pot"),
    path("admin/dc/perks", views.PerksAdminView.as_view(), name="admin-dc-perks"),
    path(
        "admin/dc/purchases/<int:pk>",
        views.PurchaseAdminView.as_view(),
        name="admin-dc-purchase",
    ),
    path("admin/dc/settings", views.SettingsAdminView.as_view(), name="admin-dc-settings"),
    path("dc/ranks", views.BoardView.as_view(), name="dc-ranks"),
    path("admin/dc/spotlights", views.SpotlightAdminView.as_view(), name="admin-dc-spotlights"),
    path("admin/dc/backpay", views.BackpayAdminView.as_view(), name="admin-dc-backpay"),
]
