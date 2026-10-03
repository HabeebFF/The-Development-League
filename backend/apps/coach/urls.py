from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("coach/knowledge", views.KnowledgeEntryViewSet, basename="coach-knowledge")

urlpatterns = [
    *router.urls,
    path("coach/weapons", views.WeaponListView.as_view(), name="coach-weapons"),
    path("coach/weapons/<int:weapon_id>", views.WeaponNameView.as_view(), name="coach-weapon"),
    path("coach/teams/<slug:slug>/profile", views.TeamProfileView.as_view(), name="coach-profile"),
    path("coach/teams/<slug:slug>/reports", views.TeamReportsView.as_view(), name="coach-reports"),
    path("coach/reports", views.ReportListView.as_view(), name="coach-report-list"),
    path("coach/reports/<int:pk>", views.ReportView.as_view(), name="coach-report"),
]
