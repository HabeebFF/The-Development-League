from django.urls import path

from . import views

urlpatterns = [
    path("matches/<int:pk>/zones", views.MatchZonesView.as_view(), name="match-zones"),
    path("matches/<int:pk>/rotations", views.MatchRotationsView.as_view(), name="match-rotations"),
    path("matches/<int:pk>/replay", views.MatchReplayView.as_view(), name="match-replay"),
    path(
        "matches/<int:pk>/redraft-rotations",
        views.MatchRedraftView.as_view(),
        name="match-rotations-redraft",
    ),
    path(
        "matches/<int:pk>/rotations/<slug:team_slug>",
        views.TeamRotationView.as_view(),
        name="team-rotation",
    ),
    path(
        "matches/<int:pk>/rotations/<slug:team_slug>/confirm",
        views.ConfirmRotationView.as_view(),
        name="team-rotation-confirm",
    ),
    path(
        "matches/<int:pk>/rotations/<slug:team_slug>/reset",
        views.ResetRotationView.as_view(),
        name="team-rotation-reset",
    ),
]
