from django.urls import path

from . import views

urlpatterns = [
    path("tournaments", views.TournamentListView.as_view(), name="tournaments"),
    path("tournaments/<slug:slug>", views.TournamentView.as_view(), name="tournament"),
    path(
        "tournaments/<slug:slug>/players", views.TopPlayersView.as_view(), name="tournament-players"
    ),
    path("tournaments/<slug:slug>/me", views.MyEntryView.as_view(), name="tournament-me"),
    path(
        "tournaments/<slug:slug>/register",
        views.MyEntryView.as_view(action="register"),
        name="tournament-register",
    ),
    path(
        "tournaments/<slug:slug>/withdraw",
        views.MyEntryView.as_view(action="withdraw"),
        name="tournament-withdraw",
    ),
    path(
        "admin/tournaments/<slug:slug>/invite-next",
        views.InviteNextView.as_view(),
        name="admin-tournament-invite-next",
    ),
    path(
        "admin/tournaments/<slug:slug>/qualifier",
        views.QualifierView.as_view(),
        name="admin-tournament-qualifier",
    ),
    path(
        "admin/tournaments/<slug:slug>/entries",
        views.StaffEntriesView.as_view(),
        name="admin-tournament-entries",
    ),
    path(
        "admin/tournaments/<slug:slug>/entries/<int:pk>/remove",
        views.StaffRemoveEntryView.as_view(),
        name="admin-tournament-entry-remove",
    ),
    path(
        "admin/tournaments/<slug:slug>/advance",
        views.AdvanceView.as_view(),
        name="admin-tournament-advance",
    ),
    path(
        "admin/tournaments/<slug:slug>/cancel",
        views.CancelView.as_view(),
        name="admin-tournament-cancel",
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
