from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import O365ConnectionView, ProjectCommunicationViewSet

router = SimpleRouter(trailing_slash=True)
router.register("projects", ProjectCommunicationViewSet, basename="project-communication")

urlpatterns = [
    path("o365/", O365ConnectionView.as_view(), name="o365-connection"),
    *router.urls,
]
