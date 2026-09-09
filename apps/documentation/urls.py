from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import DocSpaceViewSet, PublicDocsView

router = SimpleRouter(trailing_slash=True)
router.register("", DocSpaceViewSet, basename="doc-space")

urlpatterns = [
    path("public/<str:token>/", PublicDocsView.as_view(), name="doc-public"),
    *router.urls,
]
