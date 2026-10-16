from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register(
    "admin/predictions/wallets", views.WalletAdminViewSet, basename="admin-predictions-wallet"
)

urlpatterns = [
    *router.urls,
    path("predictions/wallet", views.WalletView.as_view(), name="predictions-wallet"),
    path(
        "predictions/wallet/entries",
        views.WalletEntriesView.as_view(),
        name="predictions-wallet-entries",
    ),
]
