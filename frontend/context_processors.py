"""Template context shared by every rendered page."""
import logging
import time

from .api import APIClient

logger = logging.getLogger(__name__)
UNREAD_REFRESH_SECONDS = 30
SKIPPED_PREFIXES = ("/api/", "/static/", "/media/", "/health/", "/admin/")


def notifications(request):
    """Expose the unread notification count (cached in the session for a few seconds) to the navbar."""
    session = getattr(request, "session", None)
    if session is None or not session.get("api_access") or request.path.startswith(SKIPPED_PREFIXES):
        return {}
    now = time.time()
    if now - float(session.get("notif_unread_checked_at", 0)) > UNREAD_REFRESH_SECONDS:
        try:
            _, payload, _ = APIClient(request).get("/notifications/unread-count/")
            session["notif_unread"] = int(payload.get("unread_count", 0)) if isinstance(payload, dict) else 0
        except Exception:  # the navbar badge must never break a page
            logger.warning("notification_badge_refresh_failed", exc_info=True)
            session.setdefault("notif_unread", 0)
        session["notif_unread_checked_at"] = now
    return {"unread_notification_count": session.get("notif_unread", 0)}
