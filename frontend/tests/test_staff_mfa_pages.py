from unittest.mock import patch

from django.shortcuts import redirect
from django.test import TestCase, override_settings
from django.urls import reverse


class StaffMFABrowserFlowTests(TestCase):
    def test_password_login_stores_only_pending_challenge_and_rotates_session(self):
        session = self.client.session
        session["preauth_marker"] = "retained"
        session.save()
        old_session_key = session.session_key
        response_payload = {
            "mfa_required": True,
            "mfa_challenge_id": "06a0a008-bbcc-40b1-a3dc-067d5ca8392b",
            "masked_email": "a***@example.test",
            "resend_after": 60,
            "user": {"role": "staff"},
        }
        with patch("frontend.views.APIClient.post", return_value=(202, response_payload, {})):
            response = self.client.post(
                reverse("login"),
                {"email": "agent@example.test", "password": "Correct!Password95"},
            )

        self.assertRedirects(response, reverse("staff-mfa"), fetch_redirect_response=False)
        pending = self.client.session
        self.assertNotEqual(pending.session_key, old_session_key)
        self.assertEqual(pending["staff_mfa_challenge_id"], response_payload["mfa_challenge_id"])
        self.assertEqual(pending["staff_mfa_masked_email"], response_payload["masked_email"])
        self.assertNotIn("api_access", pending)
        self.assertNotIn("api_refresh", pending)

    def test_mfa_page_does_not_expose_server_held_challenge_id(self):
        session = self.client.session
        session["staff_mfa_challenge_id"] = "06a0a008-bbcc-40b1-a3dc-067d5ca8392b"
        session["staff_mfa_masked_email"] = "a***@example.test"
        session.save()

        response = self.client.get(reverse("staff-mfa"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertContains(response, "a***@example.test")
        self.assertContains(response, 'name="code"')
        self.assertNotContains(response, "06a0a008-bbcc-40b1-a3dc-067d5ca8392b")

    def test_successful_mfa_rotates_session_and_only_then_stores_api_tokens(self):
        session = self.client.session
        session["staff_mfa_challenge_id"] = "06a0a008-bbcc-40b1-a3dc-067d5ca8392b"
        session["staff_mfa_masked_email"] = "a***@example.test"
        session.save()
        old_session_key = session.session_key
        verified_payload = {
            "access": "staff-access-token",
            "refresh": "staff-refresh-token",
            "staff_password_change_required": False,
            "staff_security_setup_required": False,
            "user": {"id": "7", "email": "agent@example.test", "role": "staff"},
        }
        with patch("frontend.views.APIClient.post", return_value=(200, verified_payload, {})), patch(
            "frontend.views.redirect_after_login", return_value=redirect("/support/dashboard/")
        ):
            response = self.client.post(reverse("staff-mfa"), {"code": "123456", "action": "verify"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/support/dashboard/")
        stored = self.client.session
        self.assertNotEqual(stored.session_key, old_session_key)
        self.assertEqual(stored["api_access"], "staff-access-token")
        self.assertEqual(stored["api_refresh"], "staff-refresh-token")
        self.assertEqual(stored["api_role"], "staff")
        self.assertNotIn("staff_mfa_challenge_id", stored)

    @override_settings(SECURE_CSP_ENABLED=True)
    def test_auth_progress_markup_remains_compatible_with_self_only_csp(self):
        response = self.client.get(reverse("forgot-password"))

        self.assertEqual(response.status_code, 200)
        csp = response["Content-Security-Policy"]
        self.assertIn("style-src 'self'", csp)
        self.assertNotIn("unsafe-inline", csp)
        html = response.content.decode("utf-8")
        self.assertIn("auth-flow-progress-track", html)
        self.assertNotRegex(html, r"\sstyle=")
