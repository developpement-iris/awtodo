class DefaultActiveStatusFilterMixin:
    """"Filtre d'état généralisé" (voir docs/modeles-et-api.md) : si le
    paramètre `status` est absent de la requête, restreint aux statuts
    "actifs" (`active_statuses`, à définir par la sous-classe) — sinon
    respecte exactement la sélection demandée, même si elle est purement
    "historique" (`?status=archivee`).

    ⚠️ Implémenté en surchargeant `filter_queryset()`, pas via un `method=`
    sur le filtre `status` lui-même : django-filter court-circuite un filtre
    `method=` dès que la valeur est "vide" (`MultipleChoiceFilter` sur un
    paramètre absent produit une liste vide, qui fait partie des
    `EMPTY_VALUES` de django-filter) — la méthode ne serait alors jamais
    appelée quand on a justement besoin d'agir sur l'absence du paramètre.
    `filter_queryset()` n'a pas ce problème : il s'exécute toujours."""

    active_statuses: frozenset = frozenset()

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        if "status" not in self.data:
            queryset = queryset.filter(status__in=self.active_statuses)
        return queryset
