class ListOnlyFilterMixin:
    """DRF applique `filterset_class` à `list()` **et** à `get_object()`
    (`GenericAPIView.get_object()` appelle `self.filter_queryset(...)` avant
    de résoudre le lookup) — surprenant mais réel : sans ce mixin, le filtre
    `status` par défaut (voir "Filtre d'état généralisé", docs/modeles-et-api.md)
    empêcherait `retrieve()`/toute action détail (ex. `reopen` sur un projet
    `cloture`) d'atteindre un objet dont le statut n'est pas dans le sous-
    ensemble "actif" par défaut, alors que l'appelant connaît déjà son id et
    n'a aucune raison de passer `?status=...`. Le filtrage par statut ne doit
    s'appliquer qu'aux listes, jamais à la résolution d'un objet précis."""

    def filter_queryset(self, queryset):
        if self.action == "list":
            return super().filter_queryset(queryset)
        return queryset
