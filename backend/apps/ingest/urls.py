from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import MatchParseRunsView, MatchReprocessView, UploadBatchViewSet

router = SimpleRouter(trailing_slash=False)
router.register("uploads/batches", UploadBatchViewSet, basename="upload-batch")

urlpatterns = [
    *router.urls,
    path("matches/<int:pk>/reprocess", MatchReprocessView.as_view(), name="match-reprocess"),
    path("matches/<int:pk>/parse-runs", MatchParseRunsView.as_view(), name="match-parse-runs"),
]
