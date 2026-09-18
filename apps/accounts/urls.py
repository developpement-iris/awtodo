from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ChangePasswordView,
    InvitationViewSet,
    LoginView,
    MeView,
    NotificationPreferencesView,
    OrganisationViewSet,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PasswordResetTokenView,
    PlanningPreferencesView,
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
    path("me/change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("me/notification-preferences/", NotificationPreferencesView.as_view(), name="notification-preferences"),
    path("me/planning-preferences/", PlanningPreferencesView.as_view(), name="planning-preferences"),
    # `<uuid:token>` plutôt qu'un ViewSet routé : évite toute ambiguïté avec
    # `password-reset/request/` (un routeur DRF classique sur `token` capture
    # n'importe quel segment, y compris littéralement "request").
    path("password-reset/request/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("password-reset/<uuid:token>/", PasswordResetTokenView.as_view(), name="password-reset-detail"),
    path("password-reset/<uuid:token>/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
]
