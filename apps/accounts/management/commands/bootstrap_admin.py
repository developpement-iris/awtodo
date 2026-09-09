import os

from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    help = (
        "Crée (ou met à jour) un compte administrateur à partir de variables "
        "d'environnement, pour amorcer une instance déployée sans accès shell "
        "(Render free tier). Lancé dans le buildCommand après `migrate`. "
        "Idempotent : sans les variables, ne fait rien ; si le compte existe "
        "déjà, ne réécrit que les droits (pas le mot de passe, sauf "
        "ADMIN_FORCE_PASSWORD=1)."
    )

    def handle(self, *args, **options):
        username = os.environ.get("ADMIN_USERNAME", "").strip()
        password = os.environ.get("ADMIN_PASSWORD", "")
        email = os.environ.get("ADMIN_EMAIL", "").strip()
        force_password = os.environ.get("ADMIN_FORCE_PASSWORD", "") == "1"

        if not username or not password:
            self.stdout.write(
                "ADMIN_USERNAME / ADMIN_PASSWORD absents — bootstrap admin ignoré."
            )
            return

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )

        if created or force_password:
            user.set_password(password)
        if email and user.email != email:
            user.email = email

        user.is_staff = True
        user.is_superuser = True
        user.is_platform_admin = True
        user.organisation_role = "admin"
        user.account_status = "active"
        user.save()

        action = "créé" if created else "mis à jour"
        self.stdout.write(
            self.style.SUCCESS(
                f"Compte admin {action} : {user.username} "
                f"(organisation {user.organisation_id})"
            )
        )
