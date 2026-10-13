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
    path("kills", views.KillsView.as_view(), name="kills"),
    path("ratings", views.RatingsView.as_view(), name="ratings"),
    path(
        "ratings/player/<int:player_id>", views.PlayerRatingsView.as_view(), name="player-ratings"
    ),
    path("admin/ratings", views.RatingAdminView.as_view(), name="admin-ratings"),
    path("cards", views.CardsView.as_view(), name="cards"),
    path("cards/month", views.TeamOfMonthView.as_view(), name="cards-month"),
    path("cards/specials", views.CardSpecialsView.as_view(), name="cards-specials"),
    path("cards/<int:player_id>", views.PlayerCardView.as_view(), name="player-card"),
    path("admin/cards", views.CardAdminView.as_view(), name="admin-cards"),
]
