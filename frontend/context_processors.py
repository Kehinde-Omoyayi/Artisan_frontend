"""Template context shared by every rendered page."""
import logging
import time

from .api import APIClient, APIError
from .staff_nav import staff_access_flags

logger = logging.getLogger(__name__)
UNREAD_REFRESH_SECONDS = 30
# Shoppers' badges are meaningless on staff tooling, and a manager account is
# refused by the shopper endpoints anyway, so the console is excluded outright.
SKIPPED_PREFIXES = ("/api/", "/static/", "/media/", "/health/", "/admin/", "/console/")


def _skips_badges(request, session):
    """True when this visitor never shows shopper badges."""
    return request.path.startswith(SKIPPED_PREFIXES)


def _badge_count(request, session, *, session_key, checked_key, path, log_event):
    now = time.time()
    if now - float(session.get(checked_key, 0)) <= UNREAD_REFRESH_SECONDS:
        return session.get(session_key, 0)
    try:
        _, payload, _ = APIClient(request).get(path)
        session[session_key] = int(payload.get("unread_count", 0)) if isinstance(payload, dict) else 0
    except APIError as exc:
        if exc.status_code in (401, 403):
            # Expected denial (e.g. a role without the badge scope). Not an
            # error worth a traceback; the navbar simply shows no badge.
            logger.info("%s status=%s path=%s", log_event, exc.status_code, path)
            session.setdefault(session_key, 0)
        else:
            logger.warning(
                "%s status=%s path=%s", log_event, exc.status_code, path, exc_info=True
            )
            session.setdefault(session_key, 0)
    except Exception:  # the navbar badge must never break a page
        logger.warning("%s path=%s", log_event, path, exc_info=True)
        session.setdefault(session_key, 0)
    session[checked_key] = now
    return session.get(session_key, 0)


def notifications(request):
    """Expose the unread notification count (cached in the session for a few seconds) to the navbar."""
    session = getattr(request, "session", None)
    if session is None or not session.get("api_access") or _skips_badges(request, session):
        return {}
    count = _badge_count(
        request,
        session,
        session_key="notif_unread",
        checked_key="notif_unread_checked_at",
        path="/notifications/unread-count/",
        log_event="notification_badge_refresh_failed",
    )
    return {"unread_notification_count": count}


def unread_messages(request):
    """Expose the unread *message* count separately from notifications.

    The number comes from the same per-user read watermark the inbox list and
    the read endpoint use, so opening a conversation lowers both consistently
    and polling cannot inflate it. Workflow notifications are never counted here.
    """
    session = getattr(request, "session", None)
    if session is None or not session.get("api_access") or _skips_badges(request, session):
        return {}
    count = _badge_count(
        request,
        session,
        session_key="msg_unread",
        checked_key="msg_unread_checked_at",
        path="/conversations/unread-count/",
        log_event="message_badge_refresh_failed",
    )
    return {"unread_message_count": count}


def staff_nav(request):
    """Expose permission flags used by the staff navigation (deny-by-default)."""
    # The manager console renders its own permission-filtered navigation
    # (console_nav); skip the duplicate lookups there.
    if getattr(request, "path", "").startswith("/console/"):
        return {}
    return {"staff_nav": staff_access_flags(request)}
