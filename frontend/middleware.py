"""One middleware: name the slow pages, and count what the API cost them."""
import logging
import time

from django.conf import settings

logger = logging.getLogger("frontend.timing")

#: Where a request keeps its tally. The API client adds to it; this writes it out.
TIMING_ATTR = "_artisan_api_timing"


def api_tally(request):
    """The per-request ``{"calls": n, "seconds": x, "slowest": (ms, path)}``."""
    tally = getattr(request, TIMING_ATTR, None)
    if tally is None:
        tally = {"calls": 0, "seconds": 0.0, "slowest": (0.0, "")}
        try:
            setattr(request, TIMING_ATTR, tally)
        except AttributeError:  # pragma: no cover - exotic request objects
            pass
    return tally


class PageTimingMiddleware:
    """Logs every page slower than ``SLOW_PAGE_LOG_MS`` with its API share.

    Guessing at "the frontend is slow" is how a 700 ms page gets blamed on the
    database. This says which page, how long, how many API calls it made and how
    much of the time those calls took -- the rest is template render.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.threshold_ms = int(getattr(settings, "SLOW_PAGE_LOG_MS", 500) or 500)

    def __call__(self, request):
        started = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if elapsed_ms >= self.threshold_ms:
            tally = getattr(request, TIMING_ATTR, None) or {"calls": 0, "seconds": 0.0, "slowest": (0.0, "")}
            api_ms = tally["seconds"] * 1000
            slowest_ms, slowest_path = tally["slowest"]
            logger.warning(
                "slow page %s %s %.0f ms (api %d calls %.0f ms, slowest %s %.0f ms; "
                "render %.0f ms)",
                request.method,
                request.get_full_path()[:120],
                elapsed_ms,
                tally["calls"],
                api_ms,
                slowest_path[:60] or "-",
                slowest_ms,
                max(0.0, elapsed_ms - api_ms),
            )
        response["Server-Timing"] = (
            f"api;dur={tally_seconds(request) * 1000:.0f}"
        )
        return response


def tally_seconds(request):
    tally = getattr(request, TIMING_ATTR, None)
    return tally["seconds"] if tally else 0.0


class StaticCacheMiddleware:
    """Let the browser keep a static file that is already versioned by its URL.

    ``{% asset %}`` appends ``?v=<mtime>``, so the address changes whenever the
    file changes. Those URLs can be cached for a year: the browser stops asking
    for the 24 stylesheets and scripts on every page view, and a changed file is
    a changed URL. Unversioned files (fonts, the phone-number library) keep the
    revalidate-every-time header.
    """

    IMMUTABLE = "public, max-age=31536000, immutable"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            getattr(response, "status_code", None) == 200
            and request.path.startswith("/static/")
            and "v=" in (request.META.get("QUERY_STRING") or "")
        ):
            response["Cache-Control"] = self.IMMUTABLE
        return response
