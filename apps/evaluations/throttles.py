from rest_framework.throttling import ScopedRateThrottle


class EvaluationSubmitThrottle(ScopedRateThrottle):
    """Envoi public d'une réponse : 10 / heure / IP (réglage `evaluation_submit`)."""

    scope_attr = "throttle_scope"
