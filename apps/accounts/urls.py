from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import InvitationViewSet, LoginView, MeView, OrganisationViewSet, TeamViewSet, UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("teams", TeamViewSet, basename="team")
router.register("organisations", OrganisationViewSet, basename="organisation")
router.register("invitations", InvitationViewSet, basename="invitation")

urlpatterns = router.urls + [
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
]
