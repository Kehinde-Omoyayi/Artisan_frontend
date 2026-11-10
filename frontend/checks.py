"""Startup checks for the standalone frontend.

The one thing that silently breaks every page is the API address: the frontend
builds every API path itself (``/services/categories/``, ``/payments/<id>/``),
so ``ARTISAN_API_BASE_URL`` must carry the API's ``/api/v1`` prefix. Without it
every call lands on the API root, comes back as an HTML 404, and the pages look
empty with no obvious reason. This check says so at boot, once, instead of
leaving a wall of "invalid json" warnings behind.
"""
from django.conf import settings
from django.core.checks import Error, register


@register()
def api_base_url_check(app_configs, **kwargs):
    base = str(getattr(settings, "ARTISAN_API_BASE_URL", "") or "").rstrip("/")
    if base.endswith("/api/v1"):
        return []
    return [
        Error(
            "ARTISAN_API_BASE_URL does not include the API's /api/v1 prefix.",
            hint=(
                f"It is currently '{base}'. Set ARTISAN_API_BASE_URL to the base of "
                "the API plus /api/v1, for example http://127.0.0.1:8000/api/v1 "
                "(and ARTISAN_API_ROOT_URL to http://127.0.0.1:8000). Every API call "
                "fails with an HTML 404 until this is right."
            ),
            id="frontend.E001",
        )
    ]
