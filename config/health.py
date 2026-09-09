"""Endpoint de santé pour le monitoring (UptimeRobot) de la phase Render.

Touche réellement la base (SELECT 1) : un ping régulier sert à la fois à
tenir Render éveillé (seuil de veille ~15 min) et à empêcher la mise en
pause de Supabase pour inactivité (mesurée en requêtes DB réelles).
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
