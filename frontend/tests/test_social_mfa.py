from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class StandaloneSocialMFABrowserFlowTests(TestCase):
    state = "standalone-social-state-0123456789abcdef"
    authorize_url = "https://accounts.google.com/o/oauth2/v2/auth?state=standalone-social-state-0123456789abcdef"

    def test_social_staff_callback_stores_only_pending_mfa_and_not_api_tokens(self):
        with patch("frontend.social_views.APIClient") as api_client:
            api_client.return_value.post.return_value = (
                200,
                {
                    "provider": "google",
                    "intent": "login",
                    "state": self.state,
                    "authorization_url": self.authorize_url,
                    "expires_in": 600,
                },
                {},
            )
            started = self.client.post(
                reverse("social-api-start", kwargs={"provider": "google"}),
                {"intent": "login", "next": "/support/"},
            )
        self.assertEqual(started.status_code, 302)
        self.assertEqual(started["Location"], self.authorize_url)
        old_session_key = self.client.session.session_key

        challenge_id = "06a0a008-bbcc-40b1-a3dc-067d5ca8392b"
        with patch("frontend.social_views.APIClient") as api_client:
            api_client.return_value.post.return_value = (
                200,
                {
                    "mfa_required": True,
                    "mfa_challenge_id": challenge_id,
                    "masked_email": "a***@example.test",
                    "resend_after": 60,
                    "user": {"role": "staff"},
                },
                {},
            )
            completed = self.client.get(
                reverse("social-api-callback", kwargs={"provider": "google"}),
                {"state": self.state, "code": "one-time-provider-code"},
            )

        self.assertEqual(completed.status_code, 302)
        self.assertEqual(completed["Location"], reverse("staff-mfa"))
        session = self.client.session
        self.assertNotEqual(session.session_key, old_session_key)
        self.assertEqual(session["staff_mfa_challenge_id"], challenge_id)
        self.assertEqual(session["staff_mfa_masked_email"], "a***@example.test")
        self.assertEqual(session["login_next"], "/support/")
        self.assertNotIn("api_access", session)
        self.assertNotIn("api_refresh", session)
        self.assertNotIn("social_auth_state", session)
