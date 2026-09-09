"""Fallback SPA : sert frontend/dist/index.html pour toute route non-API.

Le routage client (React Router / détection d'URL dans App.tsx, ex.
/docs/<token>, /invitations/<token>) a besoin qu'un rafraîchissement sur une
URL profonde renvoie quand même index.html. WhiteNoise sert les fichiers
existants (assets, /index.html) ; cette vue attrape le reste.

Actif uniquement quand SPA_INDEX_FILE est défini (settings staging) et que
le build existe — sinon 404, comportement inchangé en dev.
"""

from django.conf import settings
from django.http import FileResponse, Http404


def spa_index(_request):
    index_file = getattr(settings, "SPA_INDEX_FILE", None)
    if not index_file or not index_file.exists():
        raise Http404
    return FileResponse(open(index_file, "rb"), content_type="text/html")
