from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("maps", views.MapViewSet, basename="map")
router.register("admin/maps", views.MapAdminViewSet, basename="admin-map")

calibration = views.CalibrationPointViewSet
areas = views.MapAreaViewSet
urlpatterns = [
    *router.urls,
    path(
        "admin/maps/<slug:map_slug>/calibration-points",
        calibration.as_view({"get": "list", "post": "create", "put": "replace"}),
        name="calibration-points",
    ),
    path(
        "admin/maps/<slug:map_slug>/calibration-points/<int:pk>",
        calibration.as_view(
            {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
        ),
        name="calibration-point",
    ),
    path(
        "admin/maps/<slug:map_slug>/areas",
        areas.as_view({"get": "list", "post": "create"}),
        name="map-areas",
    ),
    path(
        "admin/maps/<slug:map_slug>/areas/<int:pk>",
        areas.as_view(
            {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
        ),
        name="map-area",
    ),
]
