from django.urls import path

from . import views

SESSION = "<str:date>/<str:session>"

urlpatterns = [
    path("scrims/tonight", views.TonightView.as_view(), name="scrims-tonight"),
    path("teams/<slug:slug>/scrims", views.TeamScrimsView.as_view(), name="team-scrims"),
    path(
        f"teams/<slug:slug>/scrims/{SESSION}/register",
        views.TeamSignupView.as_view(action="register"),
        name="team-scrims-register",
    ),
    path(
        f"teams/<slug:slug>/scrims/{SESSION}/withdraw",
        views.TeamSignupView.as_view(action="withdraw"),
        name="team-scrims-withdraw",
    ),
    path("admin/scrims/settings", views.StaffSettingsView.as_view(), name="admin-scrims-settings"),
    path("admin/scrims/night", views.StaffNightView.as_view(), name="admin-scrims-night"),
    path("admin/scrims/teams", views.StaffTeamsView.as_view(), name="admin-scrims-teams"),
    path("admin/scrims/log", views.StaffLogView.as_view(), name="admin-scrims-log"),
    path(
        "admin/scrims/teams/<slug:slug>/suspend",
        views.StaffSuspendView.as_view(action="suspend"),
        name="admin-scrims-suspend",
    ),
    path(
        "admin/scrims/teams/<slug:slug>/unsuspend",
        views.StaffSuspendView.as_view(action="unsuspend"),
        name="admin-scrims-unsuspend",
    ),
    path(
        f"admin/scrims/{SESSION}",
        views.StaffSessionView.as_view(),
        name="admin-scrims-session",
    ),
    path(
        f"admin/scrims/{SESSION}/add",
        views.StaffSessionView.as_view(action="add"),
        name="admin-scrims-add",
    ),
    path(
        f"admin/scrims/{SESSION}/remove",
        views.StaffSessionView.as_view(action="remove"),
        name="admin-scrims-remove",
    ),
]
