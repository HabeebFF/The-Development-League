from django.urls import path

from . import views

urlpatterns = [
    path("analytics/hit", views.HitView.as_view(), name="analytics-hit"),
    path("analytics/summary", views.SummaryView.as_view(), name="analytics-summary"),
]
