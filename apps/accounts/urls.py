from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    InvitationViewSet,
    LoginView,
    MeView,
    OrganisationViewSet,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PasswordResetTokenView,
    TeamViewSet,
    UserViewSet,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("teams", TeamViewSet, basename="team")
router.register("organisations", OrganisationViewSet, basename="organisation")
router.register("invitations", InvitationViewSet, basename="invitation")

urlpatterns = router.urls + [
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
    # `<uuid:token>` plutôt qu'un ViewSet routé : évite toute ambiguïté avec
    # `password-reset/request/` (un routeur DRF classique sur `token` capture
    # n'importe quel segment, y compris littéralement "request").
    path("password-reset/request/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("password-reset/<uuid:token>/", PasswordResetTokenView.as_view(), name="password-reset-detail"),
    path("password-reset/<uuid:token>/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
]
