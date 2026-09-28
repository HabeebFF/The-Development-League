from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("teams", views.PublicTeamViewSet, basename="team")
router.register("admin/teams", views.TeamAdminViewSet, basename="admin-team")
router.register("admin/team-aliases", views.TeamAliasViewSet, basename="admin-team-alias")
router.register("admin/players", views.PlayerAdminViewSet, basename="admin-player")
router.register("admin/rosters", views.RosterEntryViewSet, basename="admin-roster")

urlpatterns = router.urls
