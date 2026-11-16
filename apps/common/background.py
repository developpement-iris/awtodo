"""Exécution en arrière-plan sans broker (session du 2026-11-16).

Sans Redis, Celery tourne en mode « eager » : une tâche s'exécute dans la
requête HTTP qui l'a déclenchée, et l'utilisateur attend Microsoft Graph.
Avec `BACKGROUND_THREAD_TASKS=True`, la tâche part dans un fil d'exécution
du même processus et la requête répond tout de suite. Un seul fil par
processus : les tâches d'un même processus restent dans l'ordre (création
avant modification d'un événement Outlook). Une tâche en cours peut se perdre
si le processus redémarre ; acceptable pour une synchro qui se rattrape au
prochain changement. Avec un vrai broker (`CELERY_TASK_ALWAYS_EAGER=False`),
on repasse simplement par `.delay()`.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import connections

logger = logging.getLogger(__name__)

_executor = None
_executor_lock = threading.Lock()


def _get_executor():
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="awtodo-bg")
        return _executor


def _run(task, args):
    try:
        task.apply(args=args)
    except Exception:
        logger.exception("Tâche d'arrière-plan %s en échec", getattr(task, "name", task))
    finally:
        # Chaque fil a ses propres connexions : les fermer évite de laisser
        # une connexion ouverte par tâche vers la base.
        connections.close_all()


def run_in_background(task, *args):
    """À appeler après le commit (`transaction.on_commit`), comme `.delay()`."""
    if getattr(settings, "BACKGROUND_THREAD_TASKS", False) and settings.CELERY_TASK_ALWAYS_EAGER:
        _get_executor().submit(_run, task, args)
    else:
        task.delay(*args)
