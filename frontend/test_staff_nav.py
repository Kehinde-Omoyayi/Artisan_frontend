"""Deny-by-default staff access flags that drive every staff navigation item.

These tests pin down the contract the navbar, footer, hero and console depend
on: Super Staff are unrestricted, ordinary staff get exactly what their
support capabilities and manager permissions grant, a broken API can never
raise or grant anything, and non-staff accounts never hold staff flags.
"""
from unittest import mock

from django.test import SimpleTestCase, TestCase

from frontend import context_processors
from frontend.staff_nav import staff_access_flags


class StubSession(dict):
    modified = False


class StubRequest:
    def __init__(self, path="/dashboard/", session=None):
        self.path = path
        self.session = session if session is not None else StubSession()


def _staff_session():
    return StubSession({"api_access": True, "api_role": "staff"})


def _client_stub(capabilities=None, manager_session=None, capabilities_error=None, manager_error=None):
    client = mock.Mock()

    def _get(path, params=None):
        if path == "/support/cases/capabilities/":
            if capabilities_error is not None:
                raise capabilities_error
            return 200, (capabilities or {}), {}
        if path == "/manager/session/":
            if manager_error is not None:
                raise manager_error
            return 200, (manager_session or {}), {}
        raise AssertionError(f"unexpected path {path}")

    client.get.side_effect = _get
    return client


class StaffAccessFlagsTests(TestCase):
    def test_non_staff_session_gets_deny_by_default(self):
        request = StubRequest(session=StubSession({"api_access": True, "api_role": "customer"}))
        flags = staff_access_flags(request)
        self.assertTrue(flags)
        self.assertFalse(any(v for k, v in flags.items() if k.startswith("is_") or k.startswith("can_")))

    def test_anonymous_session_gets_deny_by_default(self):
        flags = staff_access_flags(StubRequest(session=StubSession()))
        self.assertFalse(flags["is_staff_account"])
        self.assertFalse(flags["is_superuser"])

    def test_super_staff_gets_everything(self):
        client = _client_stub(
            capabilities={"is_superuser": True, "is_support_staff": True, "can_view_refunds": True,
                           "can_manage_staff": True, "can_manage_roles": True},
            manager_session={"is_manager": True, "role": {"slug": "super-admin", "name": "Super Administrator"},
                             "permissions": ["analytics.overview", "staff.view", "audit.view"]},
        )
        with mock.patch("frontend.staff_nav.APIClient", return_value=client):
            flags = staff_access_flags(StubRequest(session=_staff_session()))
        self.assertTrue(flags["is_superuser"])
        self.assertTrue(flags["is_support_staff"])
        self.assertTrue(flags["can_view_manager_overview"])
        self.assertTrue(flags["can_view_refunds"])
        self.assertTrue(flags["can_manage_staff"])

    def test_finance_staff_scope_excludes_support_and_staff_admin(self):
        client = _client_stub(
            capabilities={"is_superuser": False, "is_support_staff": False},
            manager_session={"is_manager": True, "role": {"slug": "finance-manager", "name": "Finance Manager"},
                             "permissions": ["analytics.view", "analytics.financial", "config.view",
                                              "refund.view", "refund.request", "refund.approve",
                                              "payout.view", "payout.approve", "finance.reconcile",
                                              "audit.view", "export.data", "customer.view", "artisan.view",
                                              "support.view", "dispute.view"]},
        )
        with mock.patch("frontend.staff_nav.APIClient", return_value=client):
            flags = staff_access_flags(StubRequest(session=_staff_session()))
        # Finance scope: financial intelligence yes, overview no, staff admin no.
        self.assertTrue(flags["can_view_analytics_financial"])
        self.assertFalse(flags["can_view_manager_overview"])
        self.assertFalse(flags["can_view_staff"])
        self.assertFalse(flags["is_support_staff"])
        self.assertFalse(flags["can_manage_staff"])

    def test_support_staff_scope_excludes_finance_and_overview(self):
        client = _client_stub(
            capabilities={"is_superuser": False, "is_support_staff": True,
                          "can_view_refunds": True, "can_manage_staff": False},
            manager_session={"is_manager": True, "role": {"slug": "support-agent", "name": "Support Agent"},
                             "permissions": ["support.view", "support.manage", "dispute.view",
                                              "customer.view", "artisan.view", "refund.view", "refund.request"]},
        )
        with mock.patch("frontend.staff_nav.APIClient", return_value=client):
            flags = staff_access_flags(StubRequest(session=_staff_session()))
        self.assertTrue(flags["is_support_staff"])
        self.assertTrue(flags["can_view_refunds"])
        self.assertFalse(flags["can_view_manager_overview"])
        self.assertFalse(flags["can_view_analytics_financial"])
        self.assertFalse(flags["can_view_campaigns"])
        self.assertFalse(flags["can_view_config"])

    def test_api_failure_denies_everything_and_never_raises(self):
        from frontend.api import APIError

        client = _client_stub(capabilities_error=APIError(500, {"detail": "boom"}),
                               manager_error=APIError(403, {"detail": "boom"}))
        with mock.patch("frontend.staff_nav.APIClient", return_value=client):
            flags = staff_access_flags(StubRequest(session=_staff_session()))
        self.assertTrue(flags["is_staff_account"])
        self.assertFalse(flags["is_superuser"])
        self.assertFalse(flags["can_view_manager_overview"])

    def test_unexpected_exception_denies_everything_and_never_raises(self):
        client = _client_stub(capabilities_error=RuntimeError("network down"),
                               manager_error=RuntimeError("network down"))
        with mock.patch("frontend.staff_nav.APIClient", return_value=client):
            flags = staff_access_flags(StubRequest(session=_staff_session()))
        self.assertFalse(flags["can_view_manager_overview"])

    def test_flags_are_memoised_on_the_request(self):
        client = _client_stub(capabilities={"is_superuser": True},
                               manager_session={"is_manager": True, "role": {"slug": "super-admin"}, "permissions": []})
        request = StubRequest(session=_staff_session())
        with mock.patch("frontend.staff_nav.APIClient", return_value=client) as factory:
            staff_access_flags(request)
            staff_access_flags(request)
        self.assertEqual(factory.call_count, 1)


class StaffNavContextProcessorTests(SimpleTestCase):
    def test_console_pages_skip_the_staff_nav_lookups(self):
        session = StubSession({"api_access": True, "api_role": "staff"})
        request = StubRequest(path="/console/overview/", session=session)
        with mock.patch("frontend.context_processors.staff_access_flags") as flags:
            result = context_processors.staff_nav(request)
        flags.assert_not_called()
        self.assertEqual(result, {})

    def test_staff_pages_get_the_flags(self):
        session = StubSession({"api_access": True, "api_role": "staff"})
        request = StubRequest(path="/dashboard/", session=session)
        with mock.patch("frontend.context_processors.staff_access_flags", return_value={"is_superuser": True}) as flags:
            result = context_processors.staff_nav(request)
        flags.assert_called_once_with(request)
        self.assertEqual(result, {"staff_nav": {"is_superuser": True}})
