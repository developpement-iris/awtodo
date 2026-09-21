from django.test import TestCase


class SecurityHeadersMiddlewareTests(TestCase):
    def test_security_headers_present_on_ordinary_response(self):
        response = self.client.get("/api/health/")

        self.assertIn("Content-Security-Policy", response.headers)
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_does_not_override_an_existing_header(self):
        from django.http import HttpResponse

        from apps.common.middleware import SecurityHeadersMiddleware

        def get_response(request):
            response = HttpResponse()
            response["X-Frame-Options"] = "SAMEORIGIN"
            return response

        middleware = SecurityHeadersMiddleware(get_response)
        response = middleware(self.client.get("/api/health/").wsgi_request)

        self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")
