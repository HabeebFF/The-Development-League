from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register(
    "admin/predictions/wallets", views.WalletAdminViewSet, basename="admin-predictions-wallet"
)
router.register(
    "admin/predictions/fixtures", views.FixtureAdminViewSet, basename="admin-predictions-fixture"
)
router.register(
    "admin/predictions/markets", views.MarketAdminViewSet, basename="admin-predictions-market"
)

urlpatterns = [
    *router.urls,
    path(
        "admin/predictions/outcomes/<int:pk>",
        views.OutcomeAdminView.as_view(),
        name="admin-predictions-outcome",
    ),
    path("predictions/wallet", views.WalletView.as_view(), name="predictions-wallet"),
    path(
        "predictions/wallet/entries",
        views.WalletEntriesView.as_view(),
        name="predictions-wallet-entries",
    ),
    path("predictions/markets", views.MarketListView.as_view(), name="predictions-markets"),
    path(
        "predictions/markets/<int:pk>",
        views.MarketDetailView.as_view(),
        name="predictions-market",
    ),
    path("predictions/bets", views.BetsView.as_view(), name="predictions-bets"),
    path("predictions/bets/<uuid:pk>", views.BetDetailView.as_view(), name="predictions-bet"),
]
