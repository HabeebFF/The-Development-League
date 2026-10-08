from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("teams", views.PublicTeamViewSet, basename="team")
router.register("admin/teams", views.TeamAdminViewSet, basename="admin-team")
router.register("admin/team-aliases", views.TeamAliasViewSet, basename="admin-team-alias")
router.register("admin/players", views.PlayerAdminViewSet, basename="admin-player")
router.register("admin/rosters", views.RosterEntryViewSet, basename="admin-roster")
router.register("seasons", views.SeasonViewSet, basename="season")
router.register("match-days", views.MatchDayViewSet, basename="match-day")
router.register("matches", views.MatchViewSet, basename="match")
router.register("admin/scoring-rules", views.ScoringRuleViewSet, basename="admin-scoring-rule")
router.register("admin/seasons", views.SeasonAdminViewSet, basename="admin-season")
router.register("admin/stages", views.StageAdminViewSet, basename="admin-stage")
router.register("admin/groups", views.GroupAdminViewSet, basename="admin-group")
router.register("admin/match-days", views.MatchDayAdminViewSet, basename="admin-match-day")
router.register("admin/matches", views.MatchAdminViewSet, basename="admin-match")

urlpatterns = [
    *router.urls,
    path("awards", views.AwardsView.as_view(), name="awards"),
]
