"""Security headers for the standalone browser project (kept separate from the API project)."""

from django.conf import settings


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Referrer-Policy", settings.SECURE_REFERRER_POLICY)
        # HTML is never the same twice: without this a browser heuristically
        # caches a page (and its stale pickers/JS) and a server-side fix looks
        # like it never happened. JSON/static keep their own headers.
        content_type = response.get("Content-Type", "")
        if content_type.startswith("text/html"):
            response.setdefault("Cache-Control", "no-cache")
        if getattr(settings, "SECURE_CSP_ENABLED", False):
            response.setdefault("Content-Security-Policy", settings.SECURE_CSP)
        return response


class SandboxedOriginMiddleware:
    """Local-review only, switched on by ALLOW_SANDBOXED_ORIGIN=1.

    Inside a sandboxed preview frame the browser gives the page an opaque
    origin, so every form POST arrives with ``Origin: null`` and Django's CSRF
    origin check can never trust the literal string "null" — the post is
    refused no matter how fresh the token is. This rewrites that one header to
    the host the request actually reached, which is what a same-origin form
    post would have sent. Refused outright unless DEBUG is on, so it cannot
    reach a production process. A real foreign origin is never rewritten.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.META.get("HTTP_ORIGIN") == "null":
            host = request.get_host()
            request.META["HTTP_ORIGIN"] = f"{request.scheme}://{host}"
        return self.get_response(request)
