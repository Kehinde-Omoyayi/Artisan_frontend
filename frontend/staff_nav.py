"""Shared staff-access flags for templates and views.

One authoritative place computes what a signed-in staff member may see. The
flags come from the same backend responses the APIs enforce, so the frontend
never invents a decision of its own:

* ``/support/cases/capabilities/`` — support workspace scope (roles, refunds,
  staff management, promotions);
* ``/manager/session/`` — manager console scope (role slug + permission codes).

Results are memoised on the request only — nothing is cached across requests,
so role or permission changes take effect on the very next request. A page
render costs at most two API calls for staff. Every failure mode returns
deny-by-default flags and is logged; the navbar can never break the page.
"""
from __future__ import annotations

import logging

from .api import APIClient, APIError

logger = logging.getLogger(__name__)

_REQUEST_KEY = "_staff_access_flags"

_EMPTY = {
    "is_staff_account": False,
    "is_superuser": False,
    "is_support_staff": False,
    "is_manager": False,
    "role_slug": "",
    "permissions": [],
    "can_view_refunds": False,
    "can_manage_staff": False,
    "can_manage_roles": False,
    "can_review_promotions": False,
    "can_manage_risk_points": False,
    "can_view_manager_overview": False,
    "can_view_analytics_financial": False,
    "can_view_staff": False,
    "can_view_campaigns": False,
    "can_view_config": False,
    "can_view_audit": False,
    "can_view_privacy": False,
    "can_view_system_health": False,
}


def _deny(reason: str) -> dict:
    flags = dict(_EMPTY)
    flags["is_staff_account"] = True
    flags["reason"] = reason
    return flags


def _fetch_flags(request) -> dict:
    client = APIClient(request)
    flags = dict(_EMPTY)
    flags["is_staff_account"] = True

    capabilities: dict = {}
    try:
        _, payload, _ = client.get("/support/cases/capabilities/")
        capabilities = payload if isinstance(payload, dict) else {}
    except APIError as exc:
        if exc.status_code in (401, 403):
            logger.info(
                "staff_nav_capabilities_denied status=%s path=/api/v1/support/cases/capabilities/",
                exc.status_code,
            )
        else:
            logger.warning(
                "staff_nav_capabilities_failed status=%s", exc.status_code, exc_info=True
            )
    except Exception:  # a nav must never break the page
        logger.warning("staff_nav_capabilities_failed", exc_info=True)

    session_payload: dict = {}
    try:
        _, payload, _ = client.get("/manager/session/")
        session_payload = payload if isinstance(payload, dict) else {}
    except APIError as exc:
        if exc.status_code in (401, 403):
            logger.info(
                "staff_nav_manager_session_denied status=%s path=/api/v1/manager/session/",
                exc.status_code,
            )
        else:
            logger.warning(
                "staff_nav_manager_session_failed status=%s", exc.status_code, exc_info=True
            )
    except Exception:
        logger.warning("staff_nav_manager_session_failed", exc_info=True)

    permissions = session_payload.get("permissions") if isinstance(session_payload, dict) else []
    if not isinstance(permissions, list):
        permissions = []
    permission_set = {str(code) for code in permissions}

    is_superuser = bool(capabilities.get("is_superuser"))
    flags.update(
        {
            "is_superuser": is_superuser,
            "is_support_staff": bool(capabilities.get("is_support_staff")),
            "is_manager": bool(session_payload.get("is_manager")) if session_payload else False,
            "role_slug": str((session_payload.get("role") or {}).get("slug") or ""),
            "permissions": sorted(permission_set),
            "can_view_refunds": bool(capabilities.get("can_view_refunds")) or is_superuser,
            "can_manage_staff": bool(capabilities.get("can_manage_staff")) or is_superuser,
            "can_manage_roles": bool(capabilities.get("can_manage_roles")) or is_superuser,
            "can_review_promotions": bool(capabilities.get("can_review_promotions")) or is_superuser,
            "can_manage_risk_points": bool(capabilities.get("can_manage_risk_points")) or is_superuser,
            "can_view_manager_overview": "analytics.overview" in permission_set or is_superuser,
            "can_view_analytics_financial": "analytics.financial" in permission_set or is_superuser,
            "can_view_staff": "staff.view" in permission_set or is_superuser,
            "can_view_campaigns": "campaign.view" in permission_set or is_superuser,
            "can_view_config": "config.view" in permission_set or is_superuser,
            "can_view_audit": "audit.view" in permission_set or is_superuser,
            "can_view_privacy": "privacy.view" in permission_set or is_superuser,
            "can_view_system_health": "system.health" in permission_set or is_superuser,
        }
    )
    return flags


def staff_access_flags(request) -> dict:
    """Per-request access flags for the signed-in staff account.

    Returns deny-by-default flags for non-staff sessions. Never raises.
    """
    cached = getattr(request, _REQUEST_KEY, None)
    if isinstance(cached, dict):
        return cached

    def _store(flags):
        try:
            setattr(request, _REQUEST_KEY, flags)
        except Exception:
            pass
        return flags

    session = getattr(request, "session", None)
    if session is None or not session.get("api_access"):
        return _store(dict(_EMPTY))
    signed_in_role = str(session.get("api_role") or "").strip().lower() or str(
        (session.get("api_user") or {}).get("role") or ""
    ).strip().lower()
    if signed_in_role and signed_in_role != "staff":
        # A customer or artisan never holds staff flags.
        return _store(dict(_EMPTY))

    try:
        flags = _fetch_flags(request)
    except Exception:  # a nav must never break the page
        logger.warning("staff_nav_flags_failed", exc_info=True)
        flags = _deny("fetch-failed")
    return _store(flags)
