"""Endpoint de santé pour le monitoring (UptimeRobot, health check Clever).

Touche réellement la base (SELECT 1) : un ping régulier vérifie la
connexion à Supabase et empêche sa mise en pause pour inactivité
(mesurée en requêtes DB réelles).
Voir docs/deploiement-intermediaire.md.
"""

from django.db import connection
from django.http import JsonResponse


def health(_request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # pragma: no cover - dépend de l'infra
        return JsonResponse(
            {"status": "error", "database": str(exc)}, status=503
        )
    return JsonResponse({"status": "ok", "database": "ok"})
