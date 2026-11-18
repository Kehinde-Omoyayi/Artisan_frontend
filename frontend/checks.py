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


@register()
def session_cookie_check(app_configs, **kwargs):
    """Catch the cookie settings that make a browser silently drop the session.

    A Google or Apple callback is a cross-site round trip: the browser leaves
    this site, comes back, and must still present the session cookie that the
    start step wrote. Two settings break that in a way no error message
    mentions, because nothing on this side ever sees a request -- the cookie
    simply never comes back, the flow looks "expired", and the only clue is an
    age measured in decades. Say it at boot instead.
    """
    samesite = str(getattr(settings, "SESSION_COOKIE_SAMESITE", "") or "").strip().lower()
    secure = bool(getattr(settings, "SESSION_COOKIE_SECURE", False))
    name = str(getattr(settings, "SESSION_COOKIE_NAME", "sessionid") or "sessionid")

    # SameSite=None without Secure is rejected outright by Chrome and Firefox
    # (RFC 6265bis). The cookie is never stored, so every request gets a brand
    # new empty session -- including the provider callback.
    if samesite == "none" and not secure:
        return [
            Error(
                f"SESSION_COOKIE_SAMESITE=None needs SESSION_COOKIE_SECURE=True, "
                f"or the browser throws the '{name}' cookie away.",
                hint=(
                    "Over plain http:// set SESSION_COOKIE_SAMESITE=Lax (and leave "
                    "SESSION_COOKIE_SECURE=False). Over https:// set both: "
                    "SESSION_COOKIE_SAMESITE=None and SESSION_COOKIE_SECURE=True. "
                    "Until this is right every social sign-in reports 'expired or "
                    "could not be verified' because the session never survives the "
                    "trip to the provider."
                ),
                id="frontend.E002",
            )
        ]

    # SameSite=Strict is never sent on a cross-site navigation, so the return
    # leg from accounts.google.com arrives with no session at all.
    if samesite == "strict":
        return [
            Error(
                f"SESSION_COOKIE_SAMESITE=Strict drops the '{name}' cookie on the "
                "way back from the identity provider.",
                hint=(
                    "Use Lax (http:// development) or None with "
                    "SESSION_COOKIE_SECURE=True (https://). Strict is never sent "
                    "when the browser returns from accounts.google.com or "
                    "appleid.apple.com, so every social sign-in fails."
                ),
                id="frontend.E003",
            )
        ]

    # Secure over plain http: the browser refuses to store the cookie.
    if secure and not str(getattr(settings, "ARTISAN_API_ROOT_URL", "") or "").startswith("https://"):
        from django.core.checks import Warning as CheckWarning

        return [
            CheckWarning(
                f"SESSION_COOKIE_SECURE=True over a non-HTTPS site means the "
                f"browser refuses to store the '{name}' cookie.",
                hint=(
                    "On http://127.0.0.1 set SESSION_COOKIE_SECURE=False. If this "
                    "is really production, ARTISAN_API_ROOT_URL must be https://."
                ),
                id="frontend.W004",
            )
        ]
    return []
