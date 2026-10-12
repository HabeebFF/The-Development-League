from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("admin/pp/periods", views.PeriodAdminViewSet, basename="admin-pp-period")
router.register("admin/pp/tasks", views.TaskAdminViewSet, basename="admin-pp-task")
router.register(
    "admin/pp/adjustments", views.AdjustmentAdminViewSet, basename="admin-pp-adjustment"
)

urlpatterns = [
    *router.urls,
    path("admin/pp/results", views.ResultAdminView.as_view(), name="admin-pp-results"),
    path("pp", views.TableView.as_view(), name="pp"),
    path("pp/teams/<slug:slug>", views.TeamView.as_view(), name="pp-team"),
]
