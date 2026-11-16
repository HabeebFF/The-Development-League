from django.urls import path

from . import views

urlpatterns = [
    path("dc/me", views.MeView.as_view(), name="dc-me"),
    path("dc/waiting", views.WaitingView.as_view(), name="dc-waiting"),
    path("admin/dc/settings", views.SettingsAdminView.as_view(), name="admin-dc-settings"),
    path("admin/dc/backpay", views.BackpayAdminView.as_view(), name="admin-dc-backpay"),
]
