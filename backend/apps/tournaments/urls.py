from django.urls import path

from . import views

urlpatterns = [
    path("tournaments", views.TournamentListView.as_view(), name="tournaments"),
    path("tournaments/<slug:slug>", views.TournamentView.as_view(), name="tournament"),
    path(
        "tournaments/<slug:slug>/players", views.TopPlayersView.as_view(), name="tournament-players"
    ),
    path("admin/tournaments", views.StaffTournamentsView.as_view(), name="admin-tournaments"),
    path(
        "admin/tournaments/<slug:slug>",
        views.StaffTournamentView.as_view(),
        name="admin-tournament",
    ),
    path(
        "admin/tournaments/<slug:slug>/invite-top",
        views.InviteTopView.as_view(),
        name="admin-tournament-invite",
    ),
    path(
        "admin/tournaments/<slug:slug>/match-days",
        views.MoveDaysView.as_view(),
        name="admin-tournament-days",
    ),
    path(
        "admin/tournaments/<slug:slug>/payout",
        views.PayoutView.as_view(),
        name="admin-tournament-payout",
    ),
    path(
        "admin/tournaments/<slug:slug>/held", views.HeldView.as_view(), name="admin-tournament-held"
    ),
]
