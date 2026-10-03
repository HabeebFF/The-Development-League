from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register(r"teams/(?P<slug>[-\w]+)/invites", views.TeamInviteViewSet, basename="team-invite")
router.register(r"teams/(?P<slug>[-\w]+)/members", views.TeamMemberViewSet, basename="team-member")
router.register("admin/player-claims", views.PlayerClaimViewSet, basename="player-claim")
router.register("admin/staff", views.StaffViewSet, basename="staff")

urlpatterns = [
    path("site", views.SiteView.as_view(), name="site"),
    path("auth/csrf", views.CsrfView.as_view(), name="auth-csrf"),
    path("auth/login", views.LoginView.as_view(), name="auth-login"),
    path("auth/refresh", views.RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/password-reset", views.PasswordResetView.as_view(), name="password-reset"),
    path(
        "auth/password-reset/confirm",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("me", views.MeView.as_view(), name="me"),
    path("me/link-uid", views.LinkUidView.as_view(), name="me-link-uid"),
    path("invites/<str:token>", views.InviteView.as_view(), name="invite"),
    *router.urls,
]
