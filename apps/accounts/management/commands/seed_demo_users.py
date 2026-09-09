from django.core.management.base import BaseCommand

from apps.accounts.models import Team, TeamMembership, User

DEMO_USERS = [
    {"username": "achabane", "first_name": "Amine", "last_name": "Chabane"},
    {"username": "lgarnier", "first_name": "Léa", "last_name": "Garnier"},
    {"username": "mrousseau", "first_name": "Mathis", "last_name": "Rousseau"},
    {"username": "sfontaine", "first_name": "Sarah", "last_name": "Fontaine"},
]

# Compte technique, pas une personne — voir apps.accounts.models.User.is_service_account.
# Sert à tester en local, via X-Debug-User-Id, la création automatique
# d'incident sans contrainte de groupe (préfigure la future intégration
# ticketing, voir CLAUDE.md > "Stack technique" > Auth).
SERVICE_ACCOUNT_USERS = [
    {"username": "api.ticketing", "first_name": "Intégration", "last_name": "Ticketing"},
]

DEMO_TEAMS = {
    "Équipe Web": ["achabane", "lgarnier"],
    "Équipe Support": ["mrousseau", "sfontaine"],
}


class Command(BaseCommand):
    help = (
        "Crée des utilisateurs et groupes de démonstration pour le développement local "
        "(mode démo — voir CLAUDE.md, mécanisme d'identification temporaire X-Debug-User-Id). "
        "Idempotent, sûr à relancer."
    )

    def handle(self, *args, **options):
        users_by_username = {}
        for data in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=data["username"],
                defaults={"first_name": data["first_name"], "last_name": data["last_name"]},
            )
            users_by_username[data["username"]] = user
            self.stdout.write(f"{'Créé' if created else 'Existant'} : {user.username}")

        for data in SERVICE_ACCOUNT_USERS:
            user, created = User.objects.get_or_create(
                username=data["username"],
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "is_service_account": True,
                },
            )
            self.stdout.write(f"{'Créé' if created else 'Existant'} : {user.username} (compte de service)")

        for team_name, usernames in DEMO_TEAMS.items():
            team, created = Team.objects.get_or_create(name=team_name)
            for username in usernames:
                TeamMembership.objects.get_or_create(team=team, user=users_by_username[username])
            self.stdout.write(f"{'Créé' if created else 'Existant'} : groupe {team.name}")

        self.stdout.write(self.style.SUCCESS("Données de démo prêtes."))
