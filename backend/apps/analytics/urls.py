from django.urls import path

from . import views

urlpatterns = [
    path("analytics/hit", views.HitView.as_view(), name="analytics-hit"),
    path("analytics/time", views.TimeView.as_view(), name="analytics-time"),
    path("analytics/action", views.ActionView.as_view(), name="analytics-action"),
    path("analytics/summary", views.SummaryView.as_view(), name="analytics-summary"),
    path("analytics/day", views.DayView.as_view(), name="analytics-day"),
    path("analytics/timeline", views.TimelineView.as_view(), name="analytics-timeline"),
    path("analytics/people", views.PeopleView.as_view(), name="analytics-people"),
    path("analytics/actions", views.ActionsView.as_view(), name="analytics-actions"),
]
