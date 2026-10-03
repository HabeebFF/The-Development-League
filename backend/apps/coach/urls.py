from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("coach/knowledge", views.KnowledgeEntryViewSet, basename="coach-knowledge")

urlpatterns = [
    *router.urls,
    path("coach/weapons", views.WeaponListView.as_view(), name="coach-weapons"),
    path("coach/weapons/<int:weapon_id>", views.WeaponNameView.as_view(), name="coach-weapon"),
]
