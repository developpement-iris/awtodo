from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import DocSpaceViewSet, PublicDocAttachmentView, PublicDocsView

router = SimpleRouter(trailing_slash=True)
router.register("", DocSpaceViewSet, basename="doc-space")

urlpatterns = [
    path("public/<str:token>/", PublicDocsView.as_view(), name="doc-public"),
    path(
        "public/<str:token>/attachments/<uuid:attachment_id>/",
        PublicDocAttachmentView.as_view(),
        name="doc-public-attachment",
    ),
    *router.urls,
]
