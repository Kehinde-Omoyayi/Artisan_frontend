"""The catalogue the browser app renders, owned by the API.

The world geography and the institution register live in the API project
(``catalogue/data``) and are published at ``/api/v1/catalogue/...``. This module
is the frontend's only door to them:

* When both projects run on one machine the API package is importable, so the
  published JSON is read straight from ``catalogue.sources`` — no HTTP hop.
* Otherwise the same data is fetched from the API over HTTP.

Either way nothing is stored in this project, and the result is cached for
:data:`TTL` seconds so a page render never re-parses a 2 MB file.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from urllib.parse import urlencode

from django.conf import settings

logger = logging.getLogger(__name__)

TTL = 600
_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, object]] = {}

#: Set when the last read failed. The pages show this instead of an empty
#: picker that looks like real, if unlucky, data.
_LAST_ERROR: dict = {}

_BACKEND_LOGGED = False


def _backend():
    """The API's catalogue module, when this machine has it installed."""
    global _BACKEND_LOGGED
    try:
        from catalogue import sources  # noqa: WPS433 (optional import)
    except Exception as exc:  # pragma: no cover - depends on deployment layout
        if not _BACKEND_LOGGED:
            # Once is enough: this is a deployment shape, not a per-request fault.
            _BACKEND_LOGGED = True
            # Informational, not a fault: the two projects are usually separate
            # folders, so the frontend reads the catalogue from the running API
            # exactly as a browser would.
            logger.info(
                "catalogue: reading catalogue data from the API over HTTP "
                "(the API package is not importable from this folder: %s). "
                "This is normal for a standalone frontend; nothing to fix.",
                type(exc).__name__,
            )
        return None
    return sources


def _remember_error(label, exc):
    _LAST_ERROR.clear()
    _LAST_ERROR.update(
        {
            "label": label,
            "error": f"{type(exc).__name__}: {exc}",
            "at": time.time(),
        }
    )


def last_error():
    """The last failed catalogue read, or ``{}`` when the last read worked."""
    return dict(_LAST_ERROR)


def _clear_error():
    if _LAST_ERROR:
        _LAST_ERROR.clear()


def _http_json(path: str, params: dict | None = None):
    import requests  # local import: only used on the HTTP path

    base = str(getattr(settings, "ARTISAN_API_BASE_URL", "") or "").rstrip("/")
    if not base:  # pragma: no cover - configuration guard
        return None
    url = f"{base}{path}"
    if params:
        url = f"{url}?{urlencode({k: v for k, v in params.items() if v not in (None, '')})}"
    timeout = float(getattr(settings, "ARTISAN_API_TIMEOUT", 10) or 10)
    response = requests.get(
        url, timeout=timeout, headers={"Accept": "application/json"}
    )
    if response.status_code != 200:
        response.raise_for_status()
    return response.json()


def _cached(key: str, factory):
    now = time.monotonic()
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and hit[0] > now:
            return hit[1]
    value = factory()
    with _LOCK:
        _CACHE[key] = (now + TTL, value)
    return value


def _load(method: str, path: str, params: dict | None = None, *, empty=None):
    def factory():
        sources = _backend()
        if sources is not None:
            return getattr(sources, method)(*([] if params is None else [params]))
        return _http_json(path, params)

    try:
        value = _cached(f"{method}:{json.dumps(params, sort_keys=True)}", factory)
    except Exception as exc:
        # Nothing here may crash a page, but nothing here may hide either: an
        # empty picker with no log line is what made "every institution is
        # missing" invisible for hours. The traceback goes to the server log and
        # the reason is kept for the page to print.
        logger.exception("catalogue: %s failed (%s) — serving an empty result", method, path)
        _remember_error(method, exc)
        return empty if empty is not None else {}
    _clear_error()
    return value


# --------------------------------------------------------------------------
# World geography
# --------------------------------------------------------------------------


def world_geography() -> dict:
    """country -> {state: [areas]} (about 2 MB: server-side only)."""
    return _load("world_geography", "/catalogue/geography/", empty={})


def geography_index() -> dict:
    """country -> [states], small enough for the browser (~80 KB)."""
    return _load("geography_index", "/catalogue/geography/index/", empty={})


def geography_index_version() -> str:
    """Short fingerprint of the current index payload.

    The pickers fetch the index under ``?v=<this>``, so a browser that cached
    an older payload (the index used to ship with a day-long max-age) asks for
    a brand-new URL the moment the payload changes — no manual cache clearing.
    """
    import hashlib

    def factory() -> str:
        payload = geography_index() or {}
        blob = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha1(blob).hexdigest()[:12]

    try:
        return _cached("geography_index_version", factory) or "0"
    except Exception:  # pragma: no cover - defensive
        return "0"


def country_areas(slug: str) -> dict:
    def factory():
        sources = _backend()
        if sources is not None:
            return sources.country_areas(slug)
        return _http_json(f"/catalogue/geography/countries/{slug}/")

    try:
        value = _cached(f"country_areas:{slug}", factory) or {}
    except Exception as exc:
        logger.exception("catalogue: country_areas(%r) failed — serving no areas", slug)
        _remember_error("country_areas", exc)
        return {}
    _clear_error()
    return value


# --------------------------------------------------------------------------
# Institution register
# --------------------------------------------------------------------------


def catalogue_page(params) -> dict:
    # request.GET is a QueryDict: dict() would turn every value into a list.
    data = {key: params.get(key) for key in params} if hasattr(params, "get") else dict(params or {})
    payload = _load(
        "catalogue_page",
        "/catalogue/institutions/",
        data,
        empty={"count": 0, "results": [], "offset": 0, "limit": 50, "source": "catalogue"},
    )
    return payload or {"count": 0, "results": [], "offset": 0, "limit": 50, "source": "catalogue"}


def institution_record(source_id):
    payload = catalogue_page({"id": str(source_id or "")})
    rows = payload.get("results") or []
    return rows[0] if rows else None




# The profile forms import their defaults from here as well as from
# ``profile_catalogue``; keeping one copy avoids drift.
_DEFAULTS = {
    "country": "Nigeria",
    "state": "Ogun",
    "area": "Abeokuta",
    "nearest_institution": "Federal University of Agriculture, Abeokuta",
    "nearest_institution_abbreviation": "FUNAAB",
}


def defaults() -> dict:
    sources = _backend()
    return dict(getattr(sources, "DEFAULTS", _DEFAULTS) if sources else _DEFAULTS)
