def check_permission(fn, *args, catch, **kwargs):
    """Exécute une fonction de garde `_ensure_can_*` (qui lève une exception si
    l'action n'est pas permise) en mode vérification : renvoie un booléen au
    lieu de laisser l'exception remonter. Permet aux flags `permissions`
    exposés par l'API (voir CLAUDE.md > "Permissions API — flags calculés")
    de réutiliser exactement la même règle que la transition réelle plutôt que
    de la dupliquer — chaque app passe ses propres classes d'exception via
    `catch` (une seule fonction de garde ne lève jamais que les deux
    exceptions de son app : permission et validation)."""
    try:
        fn(*args, **kwargs)
        return True
    except catch:
        return False
