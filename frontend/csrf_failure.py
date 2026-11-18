"""The page that says "that request was out of date".

Django's default CSRF failure is a debug-only explanation full of internals. A
person who leaves a tab open, signs in somewhere else, or uses a second app on
the same host gets a page that looks broken rather than a page that explains.

Nothing is changed by a failed CSRF check, so this view only explains, offers a
working way forward, and never performs the action the stale form asked for.
"""

from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.urls import reverse


def csrf_failure(request, reason=""):
    # This project keeps its sign-in in the session (the API holds the account),
    # so request.user is always anonymous here.
    signed_in = bool((getattr(request, "session", None) or {}).get("api_access"))
    was_logout = str(request.path or "").rstrip("/") == reverse("logout").rstrip("/")
    if signed_in and was_logout:
        headline = "That sign-out used an old page."
        detail = (
            "Your sign-in changed after this page was opened, so the request was "
            "refused and you are still signed in. Press the button below to sign "
            "out now."
        )
        action = "logout"
    elif signed_in:
        headline = "That page was out of date."
        detail = (
            "Nothing was changed. Reload the page you were on and try again; the "
            "extra tab or an older sign-in made this request stale."
        )
        action = "back"
    else:
        headline = "That request was out of date."
        detail = (
            "Nothing was changed. Open the page again from the start; the form you "
            "sent came from an older visit."
        )
        action = "login"

    html = render_to_string(
        "auth/csrf_expired.html",
        {
            "headline": headline,
            "detail": detail,
            "action": action,
            "csrf_token_value": get_token(request),
            "logout_url": reverse("logout"),
            "home_url": reverse("home"),
            "login_url": reverse("login"),
        },
        request=request,
    )
    return HttpResponse(html, status=403, content_type="text/html; charset=utf-8")
