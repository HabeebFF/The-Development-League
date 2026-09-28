from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.league.urls")),
    path("api/v1/", include("apps.ingest.urls")),
    path("api/v1/", include("apps.maps.urls")),
    path("api/v1/", include("apps.rotations.urls")),
]

if settings.DEBUG:  # uploaded files (map images) in development; S3 serves them in production
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
