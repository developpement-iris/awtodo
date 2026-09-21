class SecurityHeadersMiddleware:
    """Applique CSP/HSTS/X-Frame-Options/X-Content-Type-Options à TOUTE
    réponse, y compris les fichiers statiques servis par WhiteNoise.

    WhiteNoiseMiddleware court-circuite la chaîne (il renvoie sa réponse
    sans appeler get_response) dès qu'il reconnaît un fichier statique, donc
    tout middleware placé après lui (SecurityMiddleware, XFrameOptionsMiddleware)
    ne s'exécute jamais sur ces réponses — c'est la cause du "DENY présent
    sur / mais absent sur /favicon-32.png" relevé par l'audit ZAP du
    2026-09-21. En se plaçant en tout premier dans MIDDLEWARE (base.py),
    cette classe reste la plus externe de la pile et s'applique donc à
    toute réponse quel que soit le middleware qui l'a produite.
    """

    CSP = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not response.has_header("Content-Security-Policy"):
            response["Content-Security-Policy"] = self.CSP
        if not response.has_header("X-Frame-Options"):
            response["X-Frame-Options"] = "DENY"
        if not response.has_header("X-Content-Type-Options"):
            response["X-Content-Type-Options"] = "nosniff"
        if request.is_secure() and not response.has_header("Strict-Transport-Security"):
            response["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
